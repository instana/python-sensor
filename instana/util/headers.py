# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from ..singletons import agent
from ..log import logger


def extract_custom_headers(tracing_scope, headers):
    try:
        for custom_header in agent.options.extra_http_headers:
            # Headers are in the following format: b'x-header-1'
            for header_pair in headers:
                if header_pair[0].decode('utf-8').lower() == custom_header.lower():
                    tracing_scope.span.set_tag("http.header.%s" % custom_header, header_pair[1].decode('utf-8'))
    except Exception:
        logger.debug("extract_custom_headers: ", exc_info=True)
