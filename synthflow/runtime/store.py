from __future__ import annotations

from dataclasses import replace

from synthflow.runtime.models import RunRecord, RuntimeEvent, WorkflowSnapshot


class RunStore:
    def create_run(self, run: RunRecord):
        raise NotImplementedError

    def update_run(self, run_id: str, **updates):
        raise NotImplementedError

    def get_run(self, run_id: str) -> RunRecord | None:
        raise NotImplementedError

    def append_event(self, event: RuntimeEvent):
        raise NotImplementedError

    def list_events(self, run_id: str, after_sequence_id: int | None = None) -> list[RuntimeEvent]:
        raise NotImplementedError

    def get_snapshot(self, run_id: str) -> WorkflowSnapshot | None:
        raise NotImplementedError


class InMemoryRunStore(RunStore):
    def __init__(self):
        self._runs: dict[str, RunRecord] = {}
        self._events: dict[str, list[RuntimeEvent]] = {}

    def create_run(self, run: RunRecord):
        self._runs[run.run_id] = replace(run)
        self._events.setdefault(run.run_id, [])

    def update_run(self, run_id: str, **updates):
        run = self._runs.get(run_id)
        if run is None:
            return None
        for key, value in updates.items():
            setattr(run, key, value)
        return replace(run)

    def get_run(self, run_id: str) -> RunRecord | None:
        run = self._runs.get(run_id)
        if run is None:
            return None
        return replace(run)

    def append_event(self, event: RuntimeEvent):
        bucket = self._events.setdefault(event.run_id, [])
        bucket.append(event)
        run = self._runs.get(event.run_id)
        if run is not None:
            # Keep lightweight run metadata in sync so callers do not need to
            # scan the full event log just to know the latest position/state.
            run.last_sequence_id = event.sequence_id
            if event.node_id is not None:
                run.current_node_id = event.node_id

    def list_events(self, run_id: str, after_sequence_id: int | None = None) -> list[RuntimeEvent]:
        events = self._events.get(run_id, [])
        if after_sequence_id is None:
            return list(events)
        return [event for event in events if event.sequence_id > after_sequence_id]

    def get_snapshot(self, run_id: str) -> WorkflowSnapshot | None:
        run = self._runs.get(run_id)
        if run is None:
            return None

        # The first snapshot implementation is intentionally derived from the
        # persisted event log so it stays simple and backend-agnostic.
        node_statuses: dict[str, str] = {}
        active_nodes: list[str] = []
        completed_nodes: list[str] = []
        failed_nodes: list[str] = []

        for event in self._events.get(run_id, []):
            if event.event != "node_state" or event.node_id is None:
                continue
            state = (event.data or {}).get("state")
            node_statuses[event.node_id] = state

        for node_id, state in node_statuses.items():
            if state == "started":
                active_nodes.append(node_id)
            elif state == "succeeded":
                completed_nodes.append(node_id)
            elif state == "failed":
                failed_nodes.append(node_id)

        return WorkflowSnapshot(
            run_id=run.run_id,
            flow_name=run.flow_name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            error=run.error,
            current_node_id=run.current_node_id,
            last_sequence_id=run.last_sequence_id,
            active_nodes=active_nodes,
            completed_nodes=completed_nodes,
            failed_nodes=failed_nodes,
            node_statuses=node_statuses,
            artifacts=list(run.artifacts),
        )
