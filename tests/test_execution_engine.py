import asyncio
import unittest

from synthflow.core.flow import Flow
from synthflow.core.node import Node
from synthflow.runtime.store import InMemoryRunStore
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


class StreamingNode(Node):
    async def run(self):
        self.emit_event("token", {"text": "hel"})
        await asyncio.sleep(0.01)
        self.emit_event("token", {"text": "lo"})
        return "hello"


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

    async def test_run_stream_emits_flow_and_node_events(self):
        flow = Flow(SuccessNode(id="success"))

        events = [event async for event in flow.run_stream()]

        self.assertEqual(
            [(event.event, event.node_id) for event in events],
            [
                ("flow_state", None),
                ("node_state", "success"),
                ("node_state", "success"),
                ("flow_state", None),
            ],
        )
        self.assertEqual(flow.last_execution.state, ExecutionState.SUCCEEDED)

    async def test_run_stream_yields_custom_node_events(self):
        flow = Flow(StreamingNode(id="streaming"))

        events = [event async for event in flow.run_stream()]

        tokens = [event.data["text"] for event in events if event.event == "token"]
        self.assertEqual(tokens, ["hel", "lo"])
        self.assertEqual(flow.last_execution.store.get_node_result("streaming"), "hello")

    async def test_context_exposes_run_id_and_sequence_ids(self):
        flow = Flow(StreamingNode(id="streaming"), run_store=InMemoryRunStore())

        events = [event async for event in flow.run_stream()]

        self.assertTrue(flow.last_execution.run_id)
        self.assertTrue(all(event.run_id == flow.last_execution.run_id for event in events))
        self.assertEqual([event.sequence_id for event in events], [1, 2, 3, 4, 5, 6])

    async def test_flow_can_build_snapshot_from_run_store(self):
        run_store = InMemoryRunStore()
        flow = Flow(SuccessNode(id="success"), run_store=run_store)

        context = await flow.run(return_context=True)
        snapshot = flow.get_run_snapshot(context.run_id)
        run = flow.get_run(context.run_id)

        self.assertIsNotNone(run)
        self.assertIsNotNone(snapshot)
        self.assertEqual(run.run_id, context.run_id)
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(snapshot.status, "succeeded")
        self.assertEqual(snapshot.completed_nodes, ["success"])
        self.assertEqual(snapshot.last_sequence_id, 4)
