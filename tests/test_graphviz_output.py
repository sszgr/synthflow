import unittest

from synthflow.core.dsl import PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node


class A(Node):
    async def run(self):
        return 1


class B(Node):
    async def run(self):
        return 2


class C(Node):
    async def run(self):
        return 3


class GraphvizOutputTests(unittest.TestCase):
    def test_to_graphviz_generates_dot(self):
        flow = Flow(A(id="a") >> B(id="b"))
        dot = flow.to_graphviz()

        self.assertIn("digraph SynthFlow", dot)
        self.assertIn("A(a)", dot)
        self.assertIn("B(b)", dot)
        self.assertIn("->", dot)

    def test_to_graphviz_contains_parallel_edge_labels(self):
        flow = Flow(
            PARALLEL(
                A(id="a1"),
                B(id="b1"),
                id="p1",
            )
            >> C(id="c1")
        )
        dot = flow.to_graphviz()

        self.assertIn("Parallel(p1)", dot)
        self.assertIn("parallel-1", dot)
        self.assertIn("parallel-2", dot)
