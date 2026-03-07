import asyncio

from synthflow.execution.context import ExecutionContext, ExecutionState


class Scheduler:
    async def run(self, start_node, context: ExecutionContext):
        # Single-run state machine: pending -> running -> terminal.
        # Context is attached to store so deep node calls can publish events.
        context.store.attach_execution_context(context)
        context.transition(ExecutionState.RUNNING, "Flow execution started")
        try:
            await start_node.execute(context.store)
        except asyncio.CancelledError as exc:
            context.error = exc
            context.transition(ExecutionState.CANCELLED, "Flow execution cancelled")
            raise
        except Exception as exc:
            context.error = exc
            context.transition(ExecutionState.FAILED, f"Flow execution failed: {exc}")
            raise
        else:
            context.transition(ExecutionState.SUCCEEDED, "Flow execution succeeded")
            return context.store
