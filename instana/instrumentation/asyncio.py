# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import wrapt
from opentracing.scope_managers.constants import ACTIVE_ATTR
from opentracing.scope_managers.contextvars import no_parent_scope

from ..configurator import config
from ..log import logger
from ..singletons import async_tracer

try:
    import asyncio

    @wrapt.patch_function_wrapper("asyncio", "ensure_future")
    def ensure_future_with_instana(wrapped, instance, argv, kwargs):
        if config["asyncio_task_context_propagation"]["enabled"] is False:
            with no_parent_scope():
                return wrapped(*argv, **kwargs)

        scope = async_tracer.scope_manager.active
        task = wrapped(*argv, **kwargs)

        if scope is not None:
            setattr(task, ACTIVE_ATTR, scope)

        return task

    if hasattr(asyncio, "create_task"):

        @wrapt.patch_function_wrapper("asyncio", "create_task")
        def create_task_with_instana(wrapped, instance, argv, kwargs):
            if config["asyncio_task_context_propagation"]["enabled"] is False:
                with no_parent_scope():
                    return wrapped(*argv, **kwargs)

            scope = async_tracer.scope_manager.active
            task = wrapped(*argv, **kwargs)

            if scope is not None:
                setattr(task, ACTIVE_ATTR, scope)

            return task

    logger.debug("Instrumenting asyncio")
except ImportError:
    pass
