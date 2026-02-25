import asyncio
class Timeout:
    def __init__(self, seconds=1.0):
        self.seconds = seconds

    async def run(self, coro, store):
        return await asyncio.wait_for(coro(), timeout=self.seconds)
