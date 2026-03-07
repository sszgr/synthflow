from synthflow.core.dsl import PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node


class Seed(Node):
    async def run(self):
        return [1, 2, 3]


class Sum(Node):
    async def run(self):
        return 6


class Max(Node):
    async def run(self):
        return 3


class Final(Node):
    async def run(self):
        return "done"


def main():
    flow = Flow(
        Seed(id="seed")
        >> PARALLEL(
            Sum(id="sum"),
            Max(id="max"),
            id="stats_parallel",
        )
        >> Final(id="final")
    )

    dot = flow.to_graphviz()
    print(dot)

    # Optional: write DOT for Graphviz tools, e.g.
    # dot -Tpng flow.dot -o flow.png
    with open("flow.dot", "w", encoding="utf-8") as f:
        f.write(dot)
    print("\nWrote flow.dot")


if __name__ == "__main__":
    main()
