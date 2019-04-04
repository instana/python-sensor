from __future__ import absolute_import

import wrapt

from ..log import logger
from ..singletons import async_tracer
from ..configurator import config

try:
    import asyncio

    @wrapt.patch_function_wrapper('asyncio','ensure_future')
    def ensure_future_with_instana(wrapped, instance, argv, kwargs):
        if config['asyncio_task_context_propagation']['enabled'] is False:
            return wrapped(*argv, **kwargs)

        scope = async_tracer.scope_manager.active
        task = wrapped(*argv, **kwargs)

        if scope is not None:
            async_tracer.scope_manager._set_task_scope(scope, task=task)

        return task

    if hasattr(asyncio, "create_task"):
        @wrapt.patch_function_wrapper('asyncio','create_task')
        def create_task_with_instana(wrapped, instance, argv, kwargs):
            if config['asyncio_task_context_propagation']['enabled'] is False:
                return wrapped(*argv, **kwargs)

            scope = async_tracer.scope_manager.active
            task = wrapped(*argv, **kwargs)

            if scope is not None:
                async_tracer.scope_manager._set_task_scope(scope, task=task)

            return task

    logger.debug("Instrumenting asyncio")
except ImportError:
    pass
