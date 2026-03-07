from synthflow.core.condition import If, Switch
from synthflow.core.parallel import Parallel


def to_dot(start_node):
    """Render flow topology as Graphviz DOT text."""
    lines = [
        "digraph SynthFlow {",
        "  rankdir=LR;",
        "  node [shape=box, style=rounded];",
    ]
    node_ids = {}
    visited = set()

    def get_node_id(node):
        key = id(node)
        if key in node_ids:
            return node_ids[key]
        node_name = f"n{len(node_ids)}"
        node_ids[key] = node_name
        lines.append(f'  {node_name} [label="{_escape(_label(node))}"];')
        return node_name

    def walk(node):
        current = get_node_id(node)
        node_key = id(node)
        if node_key in visited:
            return
        visited.add(node_key)

        for edge_label, child in _children(node):
            child_id = get_node_id(child)
            if edge_label == "next":
                lines.append(f"  {current} -> {child_id};")
            else:
                lines.append(f'  {current} -> {child_id} [label="{_escape(edge_label)}"];')
            walk(child)

    walk(start_node)
    lines.append("}")
    return "\n".join(lines)


def _label(node):
    return f"{node.__class__.__name__}({node.id})" if getattr(node, "id", None) else node.__class__.__name__


def _children(node):
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
    if getattr(node, "next_node", None):
        children.append(("next", node.next_node))
    return children


def _escape(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
