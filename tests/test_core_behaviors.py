import asyncio
import unittest

from synthflow.core.condition import IF, SWITCH
from synthflow.core.dsl import PARALLEL
from synthflow.core.flow import Flow
from synthflow.core.node import Node, ResultRef
from synthflow.plugins.retry import Retry
from synthflow.plugins.timeout import Timeout


class Numbers(Node):
    async def run(self):
        return [2, 5, 8]


class SumBranch(Node):
    async def run(self, numbers):
        return sum(numbers)


class MaxBranch(Node):
    async def run(self, numbers):
        return max(numbers)


class Collect(Node):
    async def run(self, total, peak):
        return {"total": total, "peak": peak}


class FlagSeed(Node):
    async def run(self, value):
        return value


class ValueNode(Node):
    async def run(self, value):
        return value


class Flaky(Node):
    def __init__(self, id=None):
        super().__init__(id=id)
        self.attempts = 0

    async def run(self):
        self.attempts += 1
        if self.attempts < 3:
            raise ValueError("temporary failure")
        return "ok"


class Slow(Node):
    async def run(self):
        await asyncio.sleep(0.05)
        return "done"


class AlwaysFail(Node):
    def __init__(self, id=None):
        super().__init__(id=id)
        self.attempts = 0

    async def run(self):
        self.attempts += 1
        raise RuntimeError("permanent failure")


class RaiseNow(Node):
    async def run(self):
        raise RuntimeError("branch failed")


class Shared:
    pass


class EmitSharedA(Node):
    outputs = [Shared]

    async def run(self):
        return "A"


class EmitSharedB(Node):
    outputs = [Shared]

    async def run(self):
        return "B"


class SleepProbe(Node):
    def __init__(self, tracker, id=None):
        super().__init__(id=id)
        self.tracker = tracker

    async def run(self):
        try:
            await asyncio.sleep(0.2)
            self.tracker["completed"] = True
            return "slow-done"
        except asyncio.CancelledError:
            self.tracker["cancelled"] = True
            raise


class CoreBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_runs_branches_and_merges_results(self):
        flow = Flow(
            Numbers(id="numbers")
            >> PARALLEL(
                SumBranch(id="sum").input(ResultRef("numbers")),
                MaxBranch(id="max").input(ResultRef("numbers")),
                id="stats",
            )
            >> Collect(id="collect").input(ResultRef("sum"), ResultRef("max"))
        )

        store = await flow.run()
        self.assertEqual(store.get_node_result("collect"), {"total": 15, "peak": 8})

    async def test_if_chooses_then_branch(self):
        flow = Flow(
            FlagSeed(id="flag").input(True)
            >> IF(
                condition=lambda store: bool(store.get_node_result("flag")),
                then_node=ValueNode(id="then_node").input("then"),
                else_node=ValueNode(id="else_node").input("else"),
                id="if_node",
            )
        )

        store = await flow.run()
        self.assertEqual(store.get_node_result("then_node"), "then")
        self.assertIsNone(store.get_node_result("else_node"))

    async def test_switch_chooses_default_when_key_missing(self):
        flow = Flow(
            FlagSeed(id="selector").input("unknown")
            >> SWITCH(
                selector=lambda store: store.get_node_result("selector"),
                cases={"a": ValueNode(id="case_a").input("A")},
                default=ValueNode(id="case_default").input("DEFAULT"),
                id="switch_node",
            )
        )

        store = await flow.run()
        self.assertEqual(store.get_node_result("case_default"), "DEFAULT")
        self.assertIsNone(store.get_node_result("case_a"))

    async def test_retry_retries_until_success(self):
        flaky = Flaky(id="flaky").use(Retry(retries=2, delay=0))
        flow = Flow(flaky)

        store = await flow.run()
        self.assertEqual(store.get_node_result("flaky"), "ok")
        self.assertEqual(flaky.attempts, 3)

    async def test_timeout_raises_when_node_exceeds_deadline(self):
        flow = Flow(Slow(id="slow").use(Timeout(seconds=0.01)))

        with self.assertRaises(asyncio.TimeoutError):
            await flow.run()

    async def test_retry_raises_after_all_attempts_exhausted(self):
        failing = AlwaysFail(id="always_fail").use(Retry(retries=2, delay=0))
        flow = Flow(failing)

        with self.assertRaises(RuntimeError):
            await flow.run()
        self.assertEqual(failing.attempts, 3)

    async def test_parallel_propagates_branch_exception(self):
        tracker = {"completed": False, "cancelled": False}
        flow = Flow(
            PARALLEL(
                SleepProbe(tracker=tracker, id="slow_branch"),
                RaiseNow(id="bad_branch"),
                id="parallel_with_error",
            )
        )

        with self.assertRaises(RuntimeError):
            await flow.run()
        self.assertTrue(tracker["cancelled"])
        self.assertFalse(tracker["completed"])

    async def test_parallel_conflict_overwrite_by_default(self):
        flow = Flow(
            PARALLEL(
                EmitSharedA(id="emit_a"),
                EmitSharedB(id="emit_b"),
                id="parallel_conflict_default",
            )
        )
        store = await flow.run()
        self.assertEqual(store.get(Shared), "B")

    async def test_parallel_conflict_keep_policy_preserves_first(self):
        flow = Flow(
            PARALLEL(
                EmitSharedA(id="emit_a"),
                EmitSharedB(id="emit_b"),
                id="parallel_conflict_keep",
                on_conflict="keep",
            )
        )
        store = await flow.run()
        self.assertEqual(store.get(Shared), "A")

    async def test_parallel_conflict_error_policy_raises(self):
        flow = Flow(
            PARALLEL(
                EmitSharedA(id="emit_a"),
                EmitSharedB(id="emit_b"),
                id="parallel_conflict_error",
                on_conflict="error",
            )
        )
        with self.assertRaises(ValueError):
            await flow.run()
