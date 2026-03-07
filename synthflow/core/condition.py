import asyncio

from synthflow.core.node import Node


class If(Node):
    def __init__(self, condition, then_node, else_node=None, id=None):
        super().__init__(id=id)
        self.condition = condition
        self.then_node = then_node
        self.else_node = else_node

    async def execute(self, store):
        self._record_node_event(store, "started", "Node execution started")
        try:
            # Evaluate condition once against current store snapshot.
            target = self.then_node if self.condition(store) else self.else_node
            if target is not None:
                store = await target.execute(store)
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


class Switch(Node):
    def __init__(self, selector, cases, default=None, id=None):
        super().__init__(id=id)
        self.selector = selector
        self.cases = cases
        self.default = default

    async def execute(self, store):
        self._record_node_event(store, "started", "Node execution started")
        try:
            # Missing key falls back to default branch (if provided).
            key = self.selector(store)
            target = self.cases.get(key, self.default)
            if target is not None:
                store = await target.execute(store)
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


def OR(*conditions):
    def _condition(store):
        return any(condition(store) for condition in conditions)

    return _condition


def IF(condition, then_node, else_node=None, id=None):
    return If(condition=condition, then_node=then_node, else_node=else_node, id=id)


def SWITCH(selector, cases, default=None, id=None):
    return Switch(selector=selector, cases=cases, default=default, id=id)
