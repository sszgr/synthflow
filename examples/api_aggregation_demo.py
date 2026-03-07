import asyncio

from synthflow.core.dsl import PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef
from synthflow.plugins import Retry, Timeout


class BuildRequest(Node):
    async def run(self):
        return {"user_id": "u-42", "region": "us-east"}


class FetchProfile(Node):
    async def run(self, request):
        await asyncio.sleep(0.02)
        return {"user_id": request["user_id"], "name": "Alice"}


class FetchOrders(Node):
    async def run(self, request):
        await asyncio.sleep(0.03)
        return [{"id": "o-1", "amount": 19.9}, {"id": "o-2", "amount": 49.0}]


class FetchRecommendations(Node):
    def __init__(self, id=None):
        super().__init__(id=id)
        self.attempts = 0

    async def run(self, request):
        self.attempts += 1
        await asyncio.sleep(0.01)
        if self.attempts == 1:
            raise RuntimeError("recommendation backend busy")
        return ["KB-01", "MS-02", "HD-05"]


class BuildApiResponse(Node):
    async def run(self, profile, orders, recommendations):
        return {
            "profile": profile,
            "orders": orders,
            "recommendations": recommendations,
        }


async def main():
    rec = FetchRecommendations(id="recommendations").use(Retry(retries=2, delay=0.02)).use(
        Timeout(seconds=1.0)
    )

    flow = Flow(
        BuildRequest(id="request")
        >> PARALLEL(
            FetchProfile(id="profile").input(ResultRef("request")),
            FetchOrders(id="orders").input(ResultRef("request")),
            rec.input(ResultRef("request")),
            id="fanout_calls",
        )
        >> BuildApiResponse(id="response").input(
            ResultRef("profile"),
            ResultRef("orders"),
            ResultRef("recommendations"),
        )
    )

    context = await flow.run(return_context=True)
    response = context.store.get_node_result("response")
    print("api response:", response)
    print("recommendation_attempts:", rec.attempts)
    print("flow_state:", context.state)


if __name__ == "__main__":
    asyncio.run(main())
