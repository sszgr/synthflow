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
class ExecutionContext:
    # Mutable execution bag for one flow run.
    # `events` tracks flow-level state; `node_events` tracks per-node state.
    store: DataStore = field(default_factory=DataStore)
    state: ExecutionState = ExecutionState.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events: list[ExecutionEvent] = field(default_factory=list)
    node_events: list[NodeExecutionEvent] = field(default_factory=list)
    error: Exception | None = None

    def transition(self, state: ExecutionState, message: str):
        # Keep explicit start/end timestamps for latency and troubleshooting.
        now = datetime.now(timezone.utc)
        if self.started_at is None and state == ExecutionState.RUNNING:
            self.started_at = now
        if state in {ExecutionState.SUCCEEDED, ExecutionState.FAILED, ExecutionState.CANCELLED}:
            self.finished_at = now
        self.state = state
        self.events.append(ExecutionEvent(timestamp=now, state=state, message=message))

    def record_node_event(self, node_id: str, node_type: str, state: str, message: str):
        self.node_events.append(
            NodeExecutionEvent(
                timestamp=datetime.now(timezone.utc),
                node_id=node_id,
                node_type=node_type,
                state=state,
                message=message,
            )
        )
