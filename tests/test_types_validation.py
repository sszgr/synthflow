import unittest

from synthflow.core.flow import Flow
from synthflow.core.node import Node
from synthflow.types import Field


class ParamNode(Node):
    params_schema = {"x": Field(int), "name": Field(str, required=False)}

    async def run(self, x, name=None):
        return {"x": x, "name": name}


class OutputFieldNode(Node):
    output_schema = Field(int)

    async def run(self):
        return "not-int"


class OutputDictNode(Node):
    output_schema = {"total": Field(int)}

    async def run(self):
        return {"total": "bad"}


class TypesValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_params_schema_accepts_valid_input(self):
        flow = Flow(ParamNode(id="param").input(x=3))
        store = await flow.run()
        self.assertEqual(store.get_node_result("param"), {"x": 3, "name": None})

    async def test_params_schema_rejects_invalid_type(self):
        flow = Flow(ParamNode(id="param").input(x="bad"))
        with self.assertRaises(TypeError):
            await flow.run()

    async def test_output_field_schema_rejects_invalid_type(self):
        flow = Flow(OutputFieldNode(id="out_field"))
        with self.assertRaises(TypeError):
            await flow.run()

    async def test_output_dict_schema_rejects_invalid_payload(self):
        flow = Flow(OutputDictNode(id="out_dict"))
        with self.assertRaises(TypeError):
            await flow.run()
