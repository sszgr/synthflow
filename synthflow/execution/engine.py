from synthflow.execution.context import ExecutionContext
from synthflow.execution.scheduler import Scheduler


class Engine:
    def __init__(self, scheduler=None):
        self.scheduler = scheduler or Scheduler()

    async def run(self, start_node, context: ExecutionContext | None = None):
        run_context = context or ExecutionContext()
        await self.scheduler.run(start_node, run_context)
        return run_context
