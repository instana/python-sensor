# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..singletons import agent, tracer, async_tracer
from ..log import logger
from .ctx_propagation import get_parent_span


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
            return tracer, tracer.active_span
        elif async_tracer.active_span:
            return async_tracer, async_tracer.active_span
        else:
            parent_span = get_parent_span()
            if parent_span:
                return tracer, parent_span
            return None, None
    except Exception:
        logger.debug("error while getting active tracer: ", exc_info=True)
        return None, None
