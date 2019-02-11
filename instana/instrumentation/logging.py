from __future__ import absolute_import

import wrapt
import logging
import sys

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
            # get the formatted log message
            # clients such as suds-jurko log things such as: Fault(Server: 'Server side fault example.')
            # So make sure we're working with a string
            msg = str(argv[1]) % argv[2]

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
                    scope.span.set_tag('error', True)
                    ec = scope.span.tags.get('ec', 0)
                    scope.span.set_tag('ec', ec + 1)
    except Exception as e:
        logger.debug('Exception: %s', e, exc_info=True)
    finally:
        return wrapped(*argv, **kwargs)


logger.debug('Instrumenting logging')

