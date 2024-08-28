# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Tuple

import wrapt
from opentelemetry.trace import use_span
from opentelemetry.trace.status import StatusCode

from instana.configurator import config
from instana.log import logger
from instana.span.span import InstanaSpan
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    import asyncio

    @wrapt.patch_function_wrapper("asyncio", "ensure_future")
    def ensure_future_with_instana(
        wrapped: Callable[..., asyncio.ensure_future],
        instance: object,
        argv: Tuple[object, Tuple[object, ...]],
        kwargs: Dict[str, Any],
    ) -> object:
        if (
            not config["asyncio_task_context_propagation"]["enabled"]
            or tracing_is_off()
        ):
            return wrapped(*argv, **kwargs)

        with _start_as_current_async_span() as span:
            try:
                span.set_status(StatusCode.OK)
                return wrapped(*argv, **kwargs)
            except Exception as exc:
                logger.debug(f"asyncio ensure_future_with_instana error: {exc}")

    if hasattr(asyncio, "create_task"):

        @wrapt.patch_function_wrapper("asyncio", "create_task")
        def create_task_with_instana(
            wrapped: Callable[..., asyncio.create_task],
            instance: object,
            argv: Tuple[object, Tuple[object, ...]],
            kwargs: Dict[str, Any],
        ) -> object:
            if (
                not config["asyncio_task_context_propagation"]["enabled"]
                or tracing_is_off()
            ):
                return wrapped(*argv, **kwargs)

            with _start_as_current_async_span() as span:
                try:
                    span.set_status(StatusCode.OK)
                    return wrapped(*argv, **kwargs)
                except Exception as exc:
                    logger.debug(f"asyncio create_task_with_instana error: {exc}")

    @contextmanager
    def _start_as_current_async_span() -> Iterator[InstanaSpan]:
        """
        Creates and yield a special InstanaSpan to only propagate the Asyncio
        context.
        """
        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        _time = time.time_ns()

        span = InstanaSpan(
            name="asyncio",
            context=parent_context,
            span_processor=tracer.span_processor,
            start_time=_time,
            end_time=_time,
        )
        with use_span(
            span,
            end_on_exit=False,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            yield span

    logger.debug("Instrumenting asyncio")
except ImportError:
    pass
