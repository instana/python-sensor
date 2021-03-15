# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

from __future__ import absolute_import

import sys
import wrapt
import logging
import collections

from ..log import logger
from ..singletons import tracer


@wrapt.patch_function_wrapper('logging', 'Logger._log')
def log_with_instana(wrapped, instance, argv, kwargs):
    # argv[0] = level
    # argv[1] = message
    # argv[2] = args for message
    try:
        parent_span = tracer.active_span

        # Only needed if we're tracing and serious log
        if parent_span and argv[0] >= logging.WARN:

            msg = str(argv[1])
            args = argv[2]
            if args and len(args) == 1 and isinstance(args[0], collections.Mapping) and args[0]:
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
    finally:
        return wrapped(*argv, **kwargs)


logger.debug('Instrumenting logging')

