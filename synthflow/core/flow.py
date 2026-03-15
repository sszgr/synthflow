from synthflow.core.parallel import Parallel
from synthflow.core.condition import If, Switch
import asyncio
from synthflow.execution.context import ExecutionContext
from synthflow.execution.engine import Engine
from synthflow.runtime.store import InMemoryRunStore
from synthflow.visualization.graphviz import to_dot

class Flow:
    def __init__(self, start_node, engine=None, run_store=None):
        self.start_node = self._normalize_start(start_node)
        self.engine = engine or Engine()
        # The store is injected at the flow level so multiple executions can be
        # queried later by run_id through a shared persistence backend.
        self.run_store = run_store or InMemoryRunStore()
        self.last_execution = None

    def _normalize_start(self, start_node):
        if isinstance(start_node, (list, tuple)):
            if not start_node:
                raise ValueError("Flow requires at least one node")
            root = start_node[0]
            for node in start_node[1:]:
                root >> node
            return root
        return start_node

    async def run(self, return_context=False):
        # Keep backwards compatibility: by default return DataStore.
        # `last_execution` is set before run so failures still leave diagnostics.
        context = ExecutionContext(run_store=self.run_store, flow_name=self.__class__.__name__)
        context.attach_loop(asyncio.get_running_loop())
        context.initialize_run()
        self.last_execution = context
        await self.engine.run(self.start_node, context=context)
        if return_context:
            return context
        return context.store

    async def run_stream(self):
        context = ExecutionContext(run_store=self.run_store, flow_name=self.__class__.__name__)
        context.attach_loop(asyncio.get_running_loop())
        context.initialize_run()
        self.last_execution = context

        async def runner():
            try:
                await self.engine.run(self.start_node, context=context)
            finally:
                context.close_stream()

        task = asyncio.create_task(runner())
        try:
            async for event in context.stream():
                yield event
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await task

    def get_run(self, run_id: str):
        return self.run_store.get_run(run_id)

    def get_run_events(self, run_id: str, after_sequence_id: int | None = None):
        return self.run_store.list_events(run_id, after_sequence_id=after_sequence_id)

    def get_run_snapshot(self, run_id: str):
        # Snapshot access is the read path used by reconnecting frontends.
        return self.run_store.get_snapshot(run_id)

    def visualize(self):
        print("Flow")
        for line in self._render_node(self.start_node, prefix="", is_last=True):
            print(line)

    def to_graphviz(self):
        return to_dot(self.start_node)

    def _label(self, node, edge=None):
        node_label = f"{node.__class__.__name__}({node.id})" if getattr(node, "id", None) else node.__class__.__name__
        if edge is None or edge == "next":
            return node_label
        return f"[{edge}] {node_label}"

    def _children(self, node):
        children = []
        if isinstance(node, Parallel):
            for idx, sub in enumerate(node.nodes, start=1):
                children.append((f"parallel-{idx}", sub))
        if isinstance(node, If):
            children.append(("then", node.then_node))
            if node.else_node:
                children.append(("else", node.else_node))
        if isinstance(node, Switch):
            for key, sub in node.cases.items():
                children.append((f"case:{key}", sub))
            if node.default:
                children.append(("default", node.default))
        if node.next_node:
            children.append(("next", node.next_node))
        return children

    def _render_node(self, node, prefix, is_last, edge=None):
        connector = "└── " if is_last else "├── "
        lines = [f"{prefix}{connector}{self._label(node, edge=edge)}"]
        child_prefix = prefix + ("    " if is_last else "│   ")
        children = self._children(node)
        for idx, (child_edge, child_node) in enumerate(children):
            child_is_last = idx == len(children) - 1
            lines.extend(
                self._render_node(
                    child_node,
                    prefix=child_prefix,
                    is_last=child_is_last,
                    edge=child_edge,
                )
            )
        return lines
