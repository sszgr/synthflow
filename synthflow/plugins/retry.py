import asyncio
class Retry:
    def __init__(self, retries=3, delay=0.5):
        self.retries = retries
        self.delay = delay

    async def run(self, coro, store):
        last_exc = None
        for i in range(self.retries):
            try:
                return await coro()
            except Exception as e:
                last_exc = e
                await asyncio.sleep(self.delay)
        raise last_exc
