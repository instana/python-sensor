# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

#
# This example illustrates how to carry context from a syncronous tracing context into
# an asynchronous one.
#
# In this use case, we want to launch a series of asyncronous http calls using uvloop and aiohttp
#
import asyncio

import aiohttp
import uvloop
from instana.singletons import async_tracer, tracer

uvloop.install()


async def launch_async_calls(parent_span):
    """
    Method to launch a series (1 currently) of asynchronous http calls
    using uvloop and aiohttp.  This method is run inside of an event loop
    with `asyncio.run`, `run_until_complete` or `gather`
    """

    # Now that we are inside of the event loop, first thing to do is to initialize
    # the tracing context using <parent_span> _and_ the asynchronous tracer <async_tracer>
    with async_tracer.start_active_span("launch_async_calls", child_of=parent_span):
        async with aiohttp.ClientSession() as session:
            session.get("http://127.0.0.1/api/v2/endpoint/1")
            session.get("http://127.0.0.1/api/v2/endpoint/2")
            session.get("http://127.0.0.1/api/v2/endpoint/3")


#
# Synchronous application code such as from inside a Django or Flask handler
#

# Start an ENTRY span in our synchronous execution scope
with tracer.start_active_span("launch_uvloop") as sync_scope:
    sync_scope.span.set_tag("span.kind", "entry")

    # You can also retrieve the currently active span with:
    # tracer.active_span

    # Launch our requests asynchronously
    # Enter the event loop and pass in the parent tracing context (sync_scope) manually
    asyncio.run(launch_async_calls(sync_scope.span))
