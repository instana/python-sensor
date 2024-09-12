# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


from pyramid.httpexceptions import HTTPException
from typing import TYPE_CHECKING, Dict, Any, Callable

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from instana.log import logger
from instana.singletons import tracer, agent
from instana.util.secrets import strip_secrets_from_query
from instana.propagators.format import Format

if TYPE_CHECKING:
    from pyramid.request import Request
    from pyramid.response import Response
    from pyramid.config import Configurator
    from instana.span.span import InstanaSpan
    from pyramid.registry import Registry


class InstanaTweenFactory(object):
    """A factory that provides Instana instrumentation tween for Pyramid apps"""

    def __init__(
        self, handler: Callable[["Request"], "Response"], registry: "Registry"
    ) -> None:
        self.handler = handler

    def _extract_custom_headers(
        self, span: "InstanaSpan", headers: Dict[str, Any]
    ) -> None:
        if not agent.options.extra_http_headers:
            return
        try:
            for custom_header in agent.options.extra_http_headers:
                if custom_header in headers:
                    span.set_attribute(
                        "http.header.%s" % custom_header, headers[custom_header]
                    )

        except Exception:
            logger.debug("extract_custom_headers: ", exc_info=True)

    def __call__(self, request: "Request") -> "Response":
        ctx = tracer.extract(Format.HTTP_HEADERS, dict(request.headers))

        with tracer.start_as_current_span("http", span_context=ctx) as span:
            span.set_attribute("span.kind", SpanKind.SERVER)
            span.set_attribute("http.host", request.host)
            span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
            span.set_attribute(SpanAttributes.HTTP_URL, request.path)

            self._extract_custom_headers(span, request.headers)

            if len(request.query_string):
                scrubbed_params = strip_secrets_from_query(
                    request.query_string,
                    agent.options.secrets_matcher,
                    agent.options.secrets_list,
                )
                span.set_attribute("http.params", scrubbed_params)

            response = None
            try:
                response = self.handler(request)
                if request.matched_route is not None:
                    span.set_attribute("http.path_tpl", request.matched_route.pattern)

                self._extract_custom_headers(span, response.headers)

                tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
                response.headers["Server-Timing"] = (
                    "intid;desc=%s" % span.context.trace_id
                )
            except HTTPException as e:
                response = e
                raise
            except BaseException as e:
                span.set_attribute("http.status", 500)

                # we need to explicitly populate the `message` tag with an error here
                # so that it's picked up from an SDK span
                span.set_attribute("message", str(e))
                span.record_exception(e)

                logger.debug("Pyramid Instana tween", exc_info=True)
            finally:
                if response:
                    span.set_attribute("http.status", response.status_int)

                    if 500 <= response.status_int:
                        if response.exception is not None:
                            message = str(response.exception)
                            span.record_exception(response.exception)
                        else:
                            message = response.status

                        span.set_attribute("message", message)
                        span.assure_errored()

            return response


def includeme(config: "Configurator") -> None:
    logger.debug("Instrumenting pyramid")
    config.add_tween(__name__ + ".InstanaTweenFactory")
