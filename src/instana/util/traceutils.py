# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from typing import Optional, Tuple

from instana.log import logger
from instana.singletons import agent, async_tracer, tornado_tracer, tracer
from instana.span import InstanaSpan
from instana.tracer import InstanaTracer


def extract_custom_headers(tracing_span, headers) -> None:
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are in the following format: b'x-header-1'
            for header_key, value in headers.items():
                if header_key.lower() == custom_header.lower():
                    tracing_span.set_tag("http.header.%s" % custom_header, value)
    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)


def get_active_tracer() -> Optional[InstanaTracer]:
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


def get_tracer_tuple() -> Tuple[Optional[InstanaTracer], Optional[InstanaSpan], Optional[str]]:
    active_tracer = get_active_tracer()
    if active_tracer:
        return (active_tracer, active_tracer.active_span, active_tracer.active_span.operation_name)
    elif agent.options.allow_exit_as_root:
        return (tracer, None, None)
    return (None, None, None)


def tracing_is_off() -> bool:
    return not (bool(get_active_tracer()) or agent.options.allow_exit_as_root)
