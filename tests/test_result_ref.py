import unittest

from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class Produce(Node):
    async def run(self):
        return [10, 20, 30]


class Consume(Node):
    async def run(self, value):
        return value


class ResultRefIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_index_zero_returns_first_item(self):
        flow = Flow(
            Produce(id="producer")
            >> Consume(id="consumer").input(ResultRef("producer", output_index=0))
        )
        store = await flow.run()
        self.assertEqual(store.get_node_result("consumer"), 10)

    async def test_output_index_non_zero_returns_expected_item(self):
        flow = Flow(
            Produce(id="producer")
            >> Consume(id="consumer").input(ResultRef("producer", output_index=2))
        )
        store = await flow.run()
        self.assertEqual(store.get_node_result("consumer"), 30)

    async def test_missing_result_ref_raises(self):
        flow = Flow(
            Consume(id="consumer").input(ResultRef("missing_node"))
        )
        with self.assertRaises(Exception):
            await flow.run()
