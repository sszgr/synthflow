import asyncio
from .node import Node
from .datastore import DataStore

class Parallel(Node):
    def __init__(self, *nodes, id=None, on_conflict="overwrite"):
        super().__init__(id=id)
        self.nodes = nodes
        # Conflict policy is applied when branch stores are merged into parent store.
        self.on_conflict = on_conflict

    async def execute(self, store: DataStore):
        self._record_node_event(store, "started", "Node execution started")
        try:
            # Each branch runs on a copy to avoid concurrent writes on shared store.
            tasks = [asyncio.create_task(node.execute(store.copy())) for node in self.nodes]
            task_to_branch = {task: node for task, node in zip(tasks, self.nodes)}
            pending = set(tasks)
            completed = {}

            try:
                while pending:
                    # Fail fast: as soon as one branch errors, cancel the rest.
                    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_EXCEPTION)
                    for task in done:
                        branch = task_to_branch[task]
                        exc = task.exception()
                        if exc is not None:
                            for pending_task in pending:
                                pending_task.cancel()
                            if pending:
                                await asyncio.gather(*pending, return_exceptions=True)
                            branch_id = branch.id or branch.__class__.__name__
                            raise RuntimeError(f"Parallel branch '{branch_id}' failed") from exc
                        completed[branch] = task.result()
            finally:
                # Ensure no background branch task leaks out of this node lifetime.
                for task in pending:
                    task.cancel()

            # Merge by declaration order for deterministic overwrite/keep behavior.
            for branch in self.nodes:
                branch_store = completed[branch]
                store.merge(branch_store, on_conflict=self.on_conflict)
            self._record_node_event(store, "succeeded", "Node execution succeeded")
            if self.next_node:
                return await self.next_node.execute(store)
            return store
        except asyncio.CancelledError:
            self._record_node_event(store, "cancelled", "Node execution cancelled")
            raise
        except Exception as exc:
            self._record_node_event(store, "failed", f"Node execution failed: {exc}")
            raise
