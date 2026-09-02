# (c) Copyright IBM Corp. 2026
"""Instana instrumentation for the Twisted HTTP server (``twisted.web.resource.Resource``).

Wraps ``Resource.render`` to create an entry span for every incoming HTTP
request, extract Instana trace-correlation headers, scrub query-parameter
secrets, inject correlation headers into the response, and close the span
when the Twisted request lifecycle ends via ``notifyFinish``.
"""

try:
    from typing import TYPE_CHECKING, Callable, Optional

    import wrapt
    from opentelemetry import context, trace
    from opentelemetry.semconv.trace import SpanAttributes

    from instana.log import logger
    from instana.propagators.format import Format
    from instana.singletons import agent, get_tracer
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers

    if TYPE_CHECKING:
        from twisted.python.failure import Failure
        from twisted.web.http import Request
        from twisted.web.resource import Resource

    @wrapt.patch_function_wrapper("twisted.web.resource", "Resource.render")
    def render_with_instana(
        wrapped: "Callable[..., Optional[bytes]]",
        instance: "Resource",
        argv: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> Optional[bytes]:
        """Wrapt wrapper for ``Resource.render`` that adds an entry span.

        Extracts any existing Instana trace context from the incoming request
        headers and starts a ``twisted-server`` span as a child.  The span is
        set as the active context for the synchronous duration of ``wrapped()``
        so that downstream exit instrumentation (e.g. ``twisted-client``) can
        find it.  ``finish_tracing`` is registered on the ``notifyFinish``
        deferred to close the span once the full response has been written.
        Falls back to the unwrapped call on any instrumentation error.
        """
        request = argv[0]
        span = None
        token = None
        try:
            tracer = get_tracer()

            # Extract parent context from incoming request headers
            headers_dict = {}
            parent_context = None
            if request.requestHeaders:
                headers_dict = {
                    k.decode("latin-1"): v[0].decode("utf-8")
                    for k, v in request.requestHeaders.getAllRawHeaders()
                }
                parent_context = tracer.extract(
                    Format.HTTP_HEADERS, headers_dict)

            span = tracer.start_span(
                "twisted-server", context=parent_context)

            # Set span as current so that any async work started during
            # wrapped() (e.g. outgoing Agent.request Deferreds) can find
            # this span as their parent after the event loop resumes.
            #
            # IMPORTANT: we do NOT detach the token here in the `finally`
            # block.  Twisted's render() returns NOT_DONE_YET for async
            # handlers, and the event loop only fires pending Deferreds
            # after render() has returned — by which point a `finally`
            # detach would have already removed the context, leaving
            # downstream spans (e.g. twisted-client) with no active parent.
            #
            # Instead the token is stored on the request object and detached
            # inside finish_tracing(), which is called by notifyFinish() only
            # after the full async response lifecycle has completed.
            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)

            # Extract the URL components
            host = request.getHeader("host") or ""
            scheme = (
                "https"
                if request.isSecure()
                else "http"
            )
            raw_path = request.path
            path = (
                raw_path.decode("latin-1")
                if isinstance(raw_path, bytes)
                else raw_path
            )
            url = f"{scheme}://{host}{path}"
            span.set_attribute(SpanAttributes.HTTP_URL, url)

            raw_method = request.method
            method = (
                raw_method.decode("latin-1")
                if isinstance(raw_method, bytes)
                else raw_method
            )
            span.set_attribute(SpanAttributes.HTTP_METHOD, method)

            # Query param scrubbing
            raw_query = request.uri
            query = (
                raw_query.decode("latin-1")
                if isinstance(raw_query, bytes)
                else raw_query
            )
            if "?" in query:
                qs = query.split("?", 1)[1]
                if qs:
                    cleaned_qp = strip_secrets_from_query(
                        qs,
                        agent.options.secrets_matcher,
                        agent.options.secrets_list,
                    )
                    span.set_attribute("http.params", cleaned_qp)

            # Request header tracking support
            extract_custom_headers(span, headers_dict)

            # Inject correlation headers into response
            response_headers = {}
            tracer.inject(span.context, Format.HTTP_HEADERS, response_headers)
            for key, value in response_headers.items():
                request.setHeader(key.encode("latin-1"), value.encode("utf-8"))

            # Store span and context token on the request so finish_tracing
            # can detach the token after the full async lifecycle completes.
            request._instana = span
            request._instana_token = token
            request._instana_finished = False

            finish_deferred = request.notifyFinish()
            finish_deferred.addBoth(finish_tracing, request)

            return wrapped(*argv, **kwargs)
        except Exception:
            # On instrumentation error detach immediately (we never reach
            # finish_tracing in this path) and fall through to the bare call.
            if token is not None:
                context.detach(token)
            if span is not None and span.is_recording():
                span.end()
            logger.debug("twisted server render_with_instana", exc_info=True)

        return wrapped(*argv, **kwargs)

    def finish_tracing(
        result: "Optional[Failure]", request: "Request"
    ) -> "Optional[Failure]":
        """Finish tracing when the Twisted request lifecycle completes."""
        if request._instana_finished:
            return result

        request._instana_finished = True
        span = request._instana
        token = getattr(request, "_instana_token", None)
        try:
            status_code = request.code
            if isinstance(status_code, int):
                span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)

            # Capture response headers
            response_hdrs = {
                k.decode("latin-1"): v[0].decode("utf-8")
                for k, v in request.responseHeaders.getAllRawHeaders()
            }
            extract_custom_headers(span, response_hdrs)

            if isinstance(status_code, int) and status_code >= 500:
                phrase = request.code_message.decode("latin-1")
                span.mark_as_errored({
                    "http.error": f"{status_code} {phrase}"
                })
        except Exception:
            logger.debug("twisted server finish_tracing", exc_info=True)
        finally:
            # Detach the OTel context token here — after the full async
            # response lifecycle — instead of in render_with_instana's
            # finally block.  This ensures the server span remains the
            # active context for any Deferreds started during render().
            if token is not None:
                context.detach(token)
            if span.is_recording():
                span.end()

        return result

    logger.debug("Instrumenting twisted server")
except ImportError:
    pass
