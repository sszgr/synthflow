import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from synthflow.core.datastore import DataStore


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
    timestamp: datetime
    event: str
    data: object = None
    node_id: str | None = None
    node_type: str | None = None


@dataclass
class ExecutionContext:
    # Mutable execution bag for one flow run.
    # `events` tracks flow-level state; `node_events` tracks per-node state.
    store: DataStore = field(default_factory=DataStore)
    state: ExecutionState = ExecutionState.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events: list[ExecutionEvent] = field(default_factory=list)
    node_events: list[NodeExecutionEvent] = field(default_factory=list)
    stream_events: list[StreamEvent] = field(default_factory=list)
    error: Exception | None = None
    _stream_queue: asyncio.Queue = field(default_factory=asyncio.Queue, init=False, repr=False)
    _stream_closed: bool = field(default=False, init=False, repr=False)
    _stream_sentinel: object = field(default_factory=object, init=False, repr=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False, repr=False)

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

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
        stream_event = StreamEvent(
            timestamp=timestamp or datetime.now(timezone.utc),
            event=event,
            data=data,
            node_id=node_id,
            node_type=node_type,
        )
        self.stream_events.append(stream_event)
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
