# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import sys
import wrapt
import logging
from collections.abc import Mapping
from typing import Any, Tuple, Dict, Callable

from instana.log import logger
from instana.util.traceutils import get_tracer_tuple, tracing_is_off


@wrapt.patch_function_wrapper("logging", "Logger._log")
def log_with_instana(
    wrapped: Callable[..., None],
    instance: logging.Logger,
    argv: Tuple[int, str, Tuple[Any, ...]],
    kwargs: Dict[str, Any],
) -> Callable[..., None]:
    # argv[0] = level
    # argv[1] = message
    # argv[2] = args for message
    if sys.version_info >= (3, 13):
        stacklevel = 3
    else:
        stacklevel = 2
    try:
        tracer, parent_span, _ = get_tracer_tuple()

        # Only needed if we're tracing and serious log
        if tracing_is_off() or argv[0] < logging.WARN:
            return wrapped(*argv, **kwargs, stacklevel=stacklevel)

        msg = str(argv[1])
        args = argv[2]
        if args and len(args) == 1 and isinstance(args[0], Mapping) and args[0]:
            args = args[0]

        # get the formatted log message
        msg = msg % args

        # get additional information if an exception is being handled
        parameters = None
        (t, v, tb) = sys.exc_info()
        if t is not None and v is not None:
            parameters = "{} {}".format(t, v)

        parent_context = parent_span.get_span_context() if parent_span else None

        # create logging span
        with tracer.start_as_current_span("log", span_context=parent_context) as span:
            event_attributes = {"message": msg}
            if parameters is not None:
                event_attributes.update({"parameters": parameters})
            span.add_event(name="log_with_instana", attributes=event_attributes)
            # extra tags for an error
            if argv[0] >= logging.ERROR:
                span.mark_as_errored()

    except Exception:
        logger.debug("log_with_instana:", exc_info=True)

    return wrapped(*argv, **kwargs, stacklevel=stacklevel)


logger.debug("Instrumenting logging")
