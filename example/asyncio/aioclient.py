from __future__ import absolute_import

import aiohttp
import asyncio

from instana.singletons import async_tracer, agent

async def test():
    while True:
        await asyncio.sleep(1)
        with async_tracer.start_active_span('JobRunner'):
            async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:5002/?secret=iloveyou") as response:
                        print(response.status)


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
loop.run_forever()

