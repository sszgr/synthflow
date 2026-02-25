from synthflow.core.node import Node

class If(Node):
    def __init__(self, condition, node):
        super().__init__()
        self.condition = condition
        self.node = node

    async def execute(self, store):
        if self.condition(store):
            store = await self.node.execute(store)
        if self.next_node:
            return await self.next_node.execute(store)
        return store
