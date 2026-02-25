import asyncio


class Retry:
    def __init__(self, retries=3, delay=0.5):
        self.retries = retries
        self.delay = delay

    async def run(self, call_next, store, node=None):
        last_exc = None
        attempts = self.retries + 1
        for i in range(attempts):
            try:
                return await call_next()
            except Exception as e:
                last_exc = e
                if i < attempts - 1 and self.delay > 0:
                    await asyncio.sleep(self.delay)
        raise last_exc
