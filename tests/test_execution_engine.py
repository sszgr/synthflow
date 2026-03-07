import asyncio
import unittest

from synthflow.core.flow import Flow
from synthflow.core.node import Node
from synthflow.execution.context import ExecutionState


class SuccessNode(Node):
    async def run(self):
        return "ok"


class FailNode(Node):
    async def run(self):
        raise RuntimeError("boom")


class SleepNode(Node):
    async def run(self):
        await asyncio.sleep(0.3)
        return "done"


class ExecutionEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_flow_exposes_success_execution_context(self):
        flow = Flow(SuccessNode(id="success"))

        context = await flow.run(return_context=True)

        self.assertEqual(context.state, ExecutionState.SUCCEEDED)
        self.assertIsNone(context.error)
        self.assertIsNotNone(context.started_at)
        self.assertIsNotNone(context.finished_at)
        self.assertEqual(flow.last_execution.state, ExecutionState.SUCCEEDED)
        self.assertEqual(context.store.get_node_result("success"), "ok")
        self.assertEqual([event.state for event in context.events], [ExecutionState.RUNNING, ExecutionState.SUCCEEDED])
        self.assertEqual(
            [(event.node_id, event.state) for event in context.node_events],
            [("success", "started"), ("success", "succeeded")],
        )

    async def test_flow_records_failed_execution_context(self):
        flow = Flow(FailNode(id="failure"))

        with self.assertRaises(RuntimeError):
            await flow.run()

        self.assertIsNotNone(flow.last_execution)
        self.assertEqual(flow.last_execution.state, ExecutionState.FAILED)
        self.assertIsInstance(flow.last_execution.error, RuntimeError)
        self.assertEqual([event.state for event in flow.last_execution.events], [ExecutionState.RUNNING, ExecutionState.FAILED])
        self.assertEqual(
            [(event.node_id, event.state) for event in flow.last_execution.node_events],
            [("failure", "started"), ("failure", "failed")],
        )

    async def test_cancelled_run_transitions_to_cancelled(self):
        flow = Flow(SleepNode(id="sleep"))

        task = asyncio.create_task(flow.run(return_context=True))
        await asyncio.sleep(0.05)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertIsNotNone(flow.last_execution)
        self.assertEqual(flow.last_execution.state, ExecutionState.CANCELLED)
        self.assertIsInstance(flow.last_execution.error, asyncio.CancelledError)
        self.assertEqual([event.state for event in flow.last_execution.events], [ExecutionState.RUNNING, ExecutionState.CANCELLED])
        self.assertEqual(
            [(event.node_id, event.state) for event in flow.last_execution.node_events],
            [("sleep", "started"), ("sleep", "cancelled")],
        )
