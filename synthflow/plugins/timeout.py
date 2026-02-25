import asyncio


class Timeout:
    def __init__(self, seconds=1.0):
        self.seconds = seconds

    async def run(self, call_next, store, node=None):
        return await asyncio.wait_for(call_next(), timeout=self.seconds)
