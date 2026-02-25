from synthflow.core.datastore import DataStore
from synthflow.core.parallel import Parallel
from synthflow.core.condition import If, Switch

class Flow:
    def __init__(self, start_node):
        self.start_node = self._normalize_start(start_node)

    def _normalize_start(self, start_node):
        if isinstance(start_node, (list, tuple)):
            if not start_node:
                raise ValueError("Flow requires at least one node")
            root = start_node[0]
            for node in start_node[1:]:
                root >> node
            return root
        return start_node

    async def run(self):
        store = DataStore()
        return await self.start_node.execute(store)

    def visualize(self):
        print("Flow")
        for line in self._render_node(self.start_node, prefix="", is_last=True):
            print(line)

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
