import asyncio

from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class A(Node):
    async def run(self):
        return 1


class B(Node):
    async def run(self, value):
        return value + 1


async def main():
    flow = Flow(A(id="a") >> B(id="b").input(value=ResultRef("a")))

    context = await flow.run(return_context=True)
    print("flow_state:", context.state)

    print("\nflow events:")
    for event in context.events:
        print(f"- {event.timestamp.isoformat()} | {event.state} | {event.message}")

    print("\nnode events:")
    for event in context.node_events:
        print(
            f"- {event.timestamp.isoformat()} | {event.node_id} ({event.node_type}) "
            f"| {event.state}"
        )


if __name__ == "__main__":
    asyncio.run(main())
