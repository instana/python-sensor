# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..singletons import agent, tracer, async_tracer, tornado_tracer
from ..log import logger


def extract_custom_headers(tracing_scope, headers):
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are in the following format: b'x-header-1'
            for header_key, value in headers.items():
                if header_key.lower() == custom_header.lower():
                    tracing_scope.span.set_tag("http.header.%s" % custom_header, value)
    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)


def get_active_tracer():
    try:
        if tracer.active_span:
            return tracer
        elif async_tracer.active_span:
            return async_tracer
        elif tornado_tracer.active_span:
            return tornado_tracer
        else:
            return None
    except Exception:
        # Do not try to log this with instana, as there is no active tracer and there will be an infinite loop at least
        # for PY2
        return None
