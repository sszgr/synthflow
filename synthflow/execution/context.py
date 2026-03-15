import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from synthflow.core.datastore import DataStore
from synthflow.runtime.models import RunRecord, RuntimeEvent
from synthflow.runtime.store import InMemoryRunStore, RunStore


class ExecutionState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionEvent:
    # Flow-level lifecycle transition.
    timestamp: datetime
    state: ExecutionState
    message: str


@dataclass
class NodeExecutionEvent:
    # Per-node lifecycle transition emitted by Node.execute().
    timestamp: datetime
    node_id: str
    node_type: str
    state: str
    message: str


@dataclass
class StreamEvent:
    # These fields let clients correlate streamed events back to a durable run.
    run_id: str
    sequence_id: int
    timestamp: datetime
    event: str
    data: object = None
    node_id: str | None = None
    node_type: str | None = None


@dataclass
class ExecutionContext:
    # Mutable execution bag for one flow run.
    # `events` tracks flow-level state; `node_events` tracks per-node state.
    run_id: str = field(default_factory=lambda: str(uuid4()))
    store: DataStore = field(default_factory=DataStore)
    state: ExecutionState = ExecutionState.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events: list[ExecutionEvent] = field(default_factory=list)
    node_events: list[NodeExecutionEvent] = field(default_factory=list)
    stream_events: list[StreamEvent] = field(default_factory=list)
    error: Exception | None = None
    run_store: RunStore = field(default_factory=InMemoryRunStore)
    flow_name: str = "Flow"
    _sequence_id: int = field(default=0, init=False, repr=False)
    _stream_queue: asyncio.Queue = field(default_factory=asyncio.Queue, init=False, repr=False)
    _stream_closed: bool = field(default=False, init=False, repr=False)
    _stream_sentinel: object = field(default_factory=object, init=False, repr=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False, repr=False)

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def initialize_run(self):
        # Persist an initial run record before execution starts so callers can
        # immediately fetch metadata or a snapshot by run_id.
        run = RunRecord(
            run_id=self.run_id,
            flow_name=self.flow_name,
            status=self.state.value,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self._stringify_error(self.error),
        )
        self.run_store.create_run(run)

    def transition(self, state: ExecutionState, message: str):
        # Keep explicit start/end timestamps for latency and troubleshooting.
        now = datetime.now(timezone.utc)
        if self.started_at is None and state == ExecutionState.RUNNING:
            self.started_at = now
        if state in {ExecutionState.SUCCEEDED, ExecutionState.FAILED, ExecutionState.CANCELLED}:
            self.finished_at = now
        self.state = state
        self.events.append(ExecutionEvent(timestamp=now, state=state, message=message))
        self.emit_stream_event("flow_state", {"state": state.value, "message": message}, timestamp=now)
        self.run_store.update_run(
            self.run_id,
            status=state.value,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self._stringify_error(self.error),
        )

    def record_node_event(self, node_id: str, node_type: str, state: str, message: str):
        now = datetime.now(timezone.utc)
        self.node_events.append(
            NodeExecutionEvent(
                timestamp=now,
                node_id=node_id,
                node_type=node_type,
                state=state,
                message=message,
            )
        )
        self.emit_stream_event(
            "node_state",
            {"state": state, "message": message},
            node_id=node_id,
            node_type=node_type,
            timestamp=now,
        )

    def emit_stream_event(
        self,
        event: str,
        data: object = None,
        *,
        node_id: str | None = None,
        node_type: str | None = None,
        timestamp: datetime | None = None,
    ) -> StreamEvent:
        # Sequence ids make replay and reconnect deterministic even if a client
        # disconnects in the middle of a long-running stream.
        sequence_id = self._next_sequence_id()
        stream_event = StreamEvent(
            run_id=self.run_id,
            sequence_id=sequence_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            event=event,
            data=data,
            node_id=node_id,
            node_type=node_type,
        )
        self.stream_events.append(stream_event)
        self.run_store.append_event(
            RuntimeEvent(
                run_id=stream_event.run_id,
                sequence_id=stream_event.sequence_id,
                timestamp=stream_event.timestamp,
                event=stream_event.event,
                data=stream_event.data,
                node_id=stream_event.node_id,
                node_type=stream_event.node_type,
            )
        )
        self._queue_item(stream_event)
        return stream_event

    async def stream(self):
        while True:
            item = await self._stream_queue.get()
            if item is self._stream_sentinel:
                break
            yield item

    def close_stream(self):
        if self._stream_closed:
            return
        self._stream_closed = True
        self._queue_item(self._stream_sentinel)

    def _queue_item(self, item):
        if self._stream_closed and item is not self._stream_sentinel:
            return
        if self._loop is None:
            self._stream_queue.put_nowait(item)
            return
        self._loop.call_soon_threadsafe(self._stream_queue.put_nowait, item)

    def _next_sequence_id(self) -> int:
        self._sequence_id += 1
        return self._sequence_id

    def _stringify_error(self, error: Exception | None) -> str | None:
        if error is None:
            return None
        return f"{error.__class__.__name__}: {error}"
