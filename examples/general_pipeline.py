import asyncio

from synthflow.core.dsl import IF, OR, PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef


class Message:
    pass


class Seed(Node):
    async def run(self, numbers):
        print(f"{self.id}: seed={numbers}")
        return numbers


class SumNode(Node):
    async def run(self, numbers):
        result = sum(numbers)
        print(f"{self.id}: {result}")
        return result


class MaxNode(Node):
    async def run(self, numbers):
        result = max(numbers)
        print(f"{self.id}: {result}")
        return result


class EvenCountNode(Node):
    async def run(self, numbers):
        result = len([n for n in numbers if n % 2 == 0])
        print(f"{self.id}: {result}")
        return result


class BuildSummary(Node):
    async def run(self, total, peak, even_count):
        summary = {
            "total": total,
            "peak": peak,
            "even_count": even_count,
            "score": total + peak + even_count,
        }
        print(f"{self.id}: {summary}")
        return summary


class Alert(Node):
    outputs = [Message]

    async def run(self, summary):
        message = f"ALERT score={summary['score']} total={summary['total']}"
        print(f"{self.id}: {message}")
        return message


class Normal(Node):
    outputs = [Message]

    async def run(self, summary):
        message = f"NORMAL score={summary['score']} even={summary['even_count']}"
        print(f"{self.id}: {message}")
        return message


class Finalize(Node):
    inputs = [Message]

    async def run(self, Message, peak):
        print(f"{self.id}: {Message} | peak={peak}")
        return Message


flow = Flow(
    Seed(id="seed").input([2, 5, 8, 13, 21])
    >> PARALLEL(
        SumNode(id="sum_branch").input(ResultRef("seed"))
        >> MaxNode(id="max_branch").input(ResultRef("seed")),
        EvenCountNode(id="even_branch").input(ResultRef("seed")),
        id="stats_parallel",
    )
    >> BuildSummary(id="summary").input(
        ResultRef("sum_branch"),
        ResultRef("max_branch"),
        ResultRef("even_branch"),
    )
    >> IF(
        condition=OR(
            lambda store: (store.get_node_result("sum_branch") or 0) > 40,
            lambda store: (store.get_node_result("max_branch") or 0) > 20,
        ),
        then_node=Alert(id="alert").input(ResultRef("summary")),
        else_node=Normal(id="normal").input(ResultRef("summary")),
        id="risk_if",
    )
    >> Finalize(id="finalize").input(
        peak=ResultRef("max_branch"),
    )
)

flow.visualize()

asyncio.run(flow.run())
