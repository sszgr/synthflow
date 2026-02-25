from synthflow.core.datastore import DataStore
from synthflow.core.parallel import Parallel
from synthflow.core.condition import If

class Flow:
    def __init__(self, start_node):
        self.start_node = start_node

    async def run(self):
        store = DataStore()
        return await self.start_node.execute(store)

    def visualize(self):
        self._print_node(self.start_node, 0)

    def _print_node(self, node, level):
        indent = "  " * level
        print(f"{indent}- {node.__class__.__name__}")
        if isinstance(node, Parallel):
            for sub in node.nodes:
                self._print_node(sub, level + 1)
        if isinstance(node, If):
            self._print_node(node.node, level + 1)
        if node.next_node:
            self._print_node(node.next_node, level)
