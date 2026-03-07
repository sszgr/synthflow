import asyncio

from synthflow.core.dsl import IF, OR, PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef
from synthflow.plugins import Retry, Timeout


class CustomerMessage:
    pass


class LoadOrder(Node):
    async def run(self):
        order = {
            "order_id": "ORD-1001",
            "user_id": "u-42",
            "items": [{"sku": "KB-01", "qty": 1}, {"sku": "MS-02", "qty": 2}],
            "amount": 159.0,
            "country": "US",
        }
        print(f"{self.id}: loaded order {order['order_id']}")
        return order


class FraudScore(Node):
    async def run(self, order):
        # Fake scoring logic.
        score = 35 if order["amount"] < 200 else 80
        print(f"{self.id}: fraud_score={score}")
        return score


class InventoryCheck(Node):
    async def run(self, order):
        in_stock = all(item["qty"] <= 5 for item in order["items"])
        print(f"{self.id}: in_stock={in_stock}")
        return in_stock


class ShippingQuote(Node):
    async def run(self, order):
        quote = 8.5 if order["country"] == "US" else 25.0
        print(f"{self.id}: shipping={quote}")
        return quote


class BuildCheckout(Node):
    async def run(self, order, fraud_score, in_stock, shipping):
        checkout = {
            "order_id": order["order_id"],
            "total": order["amount"] + shipping,
            "fraud_score": fraud_score,
            "in_stock": in_stock,
        }
        print(f"{self.id}: checkout={checkout}")
        return checkout


class ChargePayment(Node):
    def __init__(self, id=None):
        super().__init__(id=id)
        self.attempts = 0

    async def run(self, checkout):
        self.attempts += 1
        # Simulate transient gateway failure on first attempt.
        if self.attempts == 1:
            print(f"{self.id}: transient payment error")
            raise RuntimeError("gateway timeout")
        payment_id = f"PAY-{checkout['order_id']}"
        print(f"{self.id}: payment ok ({payment_id})")
        return payment_id


class CreateShipment(Node):
    outputs = [CustomerMessage]

    async def run(self, checkout, payment_id):
        msg = f"Order {checkout['order_id']} confirmed, payment={payment_id}"
        print(f"{self.id}: {msg}")
        return msg


class SendToManualReview(Node):
    outputs = [CustomerMessage]

    async def run(self, checkout):
        msg = f"Order {checkout['order_id']} sent to manual review"
        print(f"{self.id}: {msg}")
        return msg


class Notify(Node):
    inputs = [CustomerMessage]

    async def run(self, CustomerMessage):
        print(f"{self.id}: notify customer -> {CustomerMessage}")
        return CustomerMessage


async def main():
    payment = (
        ChargePayment(id="charge")
        .input(ResultRef("checkout"))
        .use(Retry(retries=2, delay=0.05))
        .use(Timeout(seconds=1.0))
    )

    flow = Flow(
        LoadOrder(id="load_order")
        >> PARALLEL(
            FraudScore(id="fraud").input(ResultRef("load_order")),
            InventoryCheck(id="inventory").input(ResultRef("load_order")),
            ShippingQuote(id="shipping").input(ResultRef("load_order")),
            id="risk_inventory_parallel",
        )
        >> BuildCheckout(id="checkout").input(
            ResultRef("load_order"),
            ResultRef("fraud"),
            ResultRef("inventory"),
            ResultRef("shipping"),
        )
        >> IF(
            condition=OR(
                lambda store: (store.get_node_result("fraud") or 0) > 70,
                lambda store: not bool(store.get_node_result("inventory")),
            ),
            then_node=SendToManualReview(id="manual_review").input(ResultRef("checkout")),
            else_node=payment >> CreateShipment(id="shipment").input(
                ResultRef("checkout"), ResultRef("charge")
            ),
            id="risk_gate",
        )
        >> Notify(id="notify")
    )

    flow.visualize()
    context = await flow.run(return_context=True)
    print("\nfinal_state:", context.state)
    print("payment_attempts:", payment.attempts)


if __name__ == "__main__":
    asyncio.run(main())
