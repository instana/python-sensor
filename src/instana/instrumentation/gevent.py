# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Instrumentation for the gevent package.
"""

import sys

from opentelemetry import context
import contextvars

from instana.log import logger


def instrument_gevent():
    """Adds context propagation to gevent greenlet spawning"""
    try:
        logger.debug("Instrumenting gevent")

        import gevent

        def spawn_callback(new_greenlet):
            """Handles context propagation for newly spawning greenlets"""
            parent_context = context.get_current()
            new_context = contextvars.Context()

            new_context.run(lambda: context.attach(parent_context))
            new_greenlet.gr_context = new_context

        gevent.Greenlet.add_spawn_callback(spawn_callback)
    except Exception:
        logger.debug("instrument_gevent: ", exc_info=True)


if "gevent" not in sys.modules:
    logger.debug("Instrumenting gevent: gevent not detected or loaded.  Nothing done.")
else:
    instrument_gevent()
