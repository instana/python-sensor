# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import sys
import wrapt
import logging
from collections.abc import Mapping

from ..log import logger
from ..util.traceutils import get_tracer_tuple, tracing_is_off


@wrapt.patch_function_wrapper('logging', 'Logger._log')
def log_with_instana(wrapped, instance, argv, kwargs):
    # argv[0] = level
    # argv[1] = message
    # argv[2] = args for message

    # We take into consideration if `stacklevel` is already present in `kwargs`.
    # This prevents the error `_log() got multiple values for keyword argument 'stacklevel'`
    if "stacklevel" in kwargs.keys():
        stacklevel = kwargs.pop("stacklevel")
    else:
        stacklevel = 2
        if sys.version_info >= (3, 13):
            stacklevel = 3
        
    try:
        # Only needed if we're tracing and serious log
        if tracing_is_off() or argv[0] < logging.WARN:
            return wrapped(*argv, **kwargs, stacklevel=stacklevel)

        tracer, parent_span, _ = get_tracer_tuple()

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
            parameters = '{} {}'.format(t , v)

        # create logging span
        with tracer.start_active_span('log', child_of=parent_span) as scope:
            scope.span.log_kv({ 'message': msg })
            if parameters is not None:
                scope.span.log_kv({ 'parameters': parameters })
            # extra tags for an error
            if argv[0] >= logging.ERROR:
                scope.span.mark_as_errored()
    except Exception:
        logger.debug('log_with_instana:', exc_info=True)

    return wrapped(*argv, **kwargs, stacklevel=stacklevel)


logger.debug('Instrumenting logging')

