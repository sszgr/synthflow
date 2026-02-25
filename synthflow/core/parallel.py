import asyncio
from .node import Node
from .datastore import DataStore

class Parallel(Node):
    def __init__(self, *nodes, id=None):
        super().__init__(id=id)
        self.nodes = nodes

    async def execute(self, store: DataStore):
        tasks = [node.execute(store.copy()) for node in self.nodes]
        results = await asyncio.gather(*tasks)
        # 合并
        for s in results:
            for dtype, value in s._data.items():
                store.set(dtype, value)
        if self.next_node:
            return await self.next_node.execute(store)
        return store
