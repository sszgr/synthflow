import asyncio

from synthflow.core.flow import Flow
from synthflow.core.node import Node
from synthflow.types import Field


class Add(Node):
    params_schema = {"a": Field(int), "b": Field(int)}
    output_schema = Field(int)

    async def run(self, a, b):
        return a + b


class BadOutput(Node):
    output_schema = Field(int)

    async def run(self):
        return "not-an-int"


async def main():
    print("== Valid input/output ==")
    ok_flow = Flow(Add(id="add").input(a=2, b=3))
    ok_store = await ok_flow.run()
    print("result:", ok_store.get_node_result("add"))

    print("\n== Invalid params (TypeError) ==")
    try:
        bad_params_flow = Flow(Add(id="add_bad_params").input(a="2", b=3))
        await bad_params_flow.run()
    except Exception as exc:
        print(type(exc).__name__, exc)

    print("\n== Invalid output (TypeError) ==")
    try:
        bad_output_flow = Flow(BadOutput(id="bad_output"))
        await bad_output_flow.run()
    except Exception as exc:
        print(type(exc).__name__, exc)


if __name__ == "__main__":
    asyncio.run(main())
