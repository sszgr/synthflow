from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ArtifactRecord:
    artifact_id: str
    name: str
    status: str
    media_type: str | None = None
    uri: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class NodeTraceRecord:
    run_id: str
    node_id: str
    node_type: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    input_preview: object = None
    output_preview: object = None
    error_summary: str | None = None


@dataclass
class RuntimeEvent:
    run_id: str
    sequence_id: int
    timestamp: datetime
    event: str
    data: object = None
    node_id: str | None = None
    node_type: str | None = None


@dataclass
class RunRecord:
    run_id: str
    flow_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    current_node_id: str | None = None
    last_sequence_id: int = 0
    artifacts: list[ArtifactRecord] = field(default_factory=list)


@dataclass
class WorkflowSnapshot:
    run_id: str
    flow_name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    current_node_id: str | None
    last_sequence_id: int
    active_nodes: list[str] = field(default_factory=list)
    completed_nodes: list[str] = field(default_factory=list)
    failed_nodes: list[str] = field(default_factory=list)
    node_statuses: dict[str, str] = field(default_factory=dict)
    artifacts: list[ArtifactRecord] = field(default_factory=list)

