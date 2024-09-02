# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

import asyncio

import aiohttp
from instana.singletons import async_tracer


async def test():
    while True:
        await asyncio.sleep(2)
        with async_tracer.start_active_span("JobRunner"):
            async with aiohttp.ClientSession() as session:
                # aioserver exposes /, /401, /500 & /publish
                async with session.get(
                    "http://localhost:5102/publish?secret=iloveyou"
                ) as response:
                    print(response.status)


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
loop.run_forever()
