# (c) Copyright IBM Corp. 2026
"""Instana instrumentation for the Twisted HTTP client (``twisted.web.client.Agent``).

Wraps ``Agent.request`` to create an exit span for every outgoing HTTP request,
propagate Instana correlation headers, scrub query-parameter secrets, and record
the response status code (or exception) when the returned ``Deferred`` resolves.
"""

try:
    from typing import TYPE_CHECKING, Callable, Union

    import wrapt
    from opentelemetry.context import get_current
    from opentelemetry.semconv.trace import SpanAttributes
    from twisted.python.failure import Failure
    from twisted.web.http_headers import Headers as TwistedHeaders

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import agent, get_tracer
    from instana.span.span import get_current_span
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers

    if TYPE_CHECKING:
        from twisted.internet.defer import Deferred
        from twisted.web.iweb import IResponse

        from instana.span.span import InstanaSpan

    @wrapt.patch_function_wrapper("twisted.web.client", "Agent.request")
    def request_with_instana(
        wrapped: "Callable[..., Deferred]",
        instance: object,
        argv: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> "Deferred":
        """Wrapt wrapper for ``Agent.request`` that adds an exit span.

        Starts a ``twisted-client`` span, injects Instana trace-correlation
        headers into the outgoing request, and attaches ``finish_tracing`` as
        both a callback and errback on the returned ``Deferred`` so the span is
        always closed.  Falls back to the unwrapped call on any instrumentation
        error to keep the application path safe.
        """
        try:
            parent_span = get_current_span()

            # If we're not tracing, just return
            if not parent_span.is_recording():
                return wrapped(*argv, **kwargs)

            # argv: (method, url[, headers[, bodyProducer]])
            method = argv[0]
            url = argv[1]
            headers = (
                argv[2] if len(argv) > 2 else kwargs.get("headers"))

            method_str = (
                method.decode("latin-1")
                if isinstance(method, bytes)
                else str(method)
            )
            url_str = (
                url.decode("latin-1")
                if isinstance(url, bytes)
                else str(url)
            )

            parent_context = get_current()
            tracer = get_tracer()
            span = tracer.start_span("twisted-client", context=parent_context)

            # Query param scrubbing
            parts = url_str.split("?", 1)
            span.set_attribute(SpanAttributes.HTTP_URL, parts[0])
            if len(parts) > 1 and parts[1]:
                cleaned_qp = strip_secrets_from_query(
                    parts[1],
                    agent.options.secrets_matcher,
                    agent.options.secrets_list,
                )
                span.set_attribute("http.params", cleaned_qp)

            span.set_attribute(SpanAttributes.HTTP_METHOD, method_str)

            # Build / augment headers with trace correlation
            if headers is None or not isinstance(headers, TwistedHeaders):
                headers = TwistedHeaders({})

            # Capture outgoing request headers
            headers_dict = {
                k.decode("latin-1"): v[0].decode("utf-8")
                for k, v in headers.getAllRawHeaders()
            }
            extract_custom_headers(span, headers_dict)

            # Inject Instana correlation headers
            inject_carrier = {}
            tracer.inject(span.context, Format.HTTP_HEADERS, inject_carrier)
            for key, value in inject_carrier.items():
                headers.setRawHeaders(key.encode("latin-1"), [value.encode("utf-8")])

            # Rebuild argv with the modified headers
            new_argv = (argv[0], argv[1], headers) + argv[3:]

            deferred = wrapped(*new_argv, **kwargs)

            if deferred is not None:
                deferred.addBoth(finish_tracing, span)

            return deferred
        except Exception:
            logger.debug("twisted client request_with_instana", exc_info=True)

        return wrapped(*argv, **kwargs)

    def finish_tracing(
        result: "Union[IResponse, Failure]", span: "InstanaSpan"
    ) -> "Union[IResponse, Failure]":
        """Callback/errback attached to the Agent.request Deferred."""
        try:
            if isinstance(result, Failure):
                span.record_exception(result.value)
            else:
                status_code = result.code
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)

                # Capture response headers
                headers_dict = {
                    k.decode("latin-1"): v[0].decode("utf-8")
                    for k, v in result.headers.getAllRawHeaders()
                }
                extract_custom_headers(span, headers_dict)

                if status_code >= 500:
                    span.mark_as_errored({
                        "http.error": result.phrase.decode("latin-1")
                    })
        except Exception:
            logger.debug("twisted client finish_tracing", exc_info=True)
        finally:
            if span.is_recording():
                span.end()

        return result

    logger.debug("Instrumenting twisted client")
except ImportError:
    pass
