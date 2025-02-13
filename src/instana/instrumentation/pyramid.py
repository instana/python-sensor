# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

try:
    from pyramid.httpexceptions import HTTPException
    from pyramid.path import caller_package
    from pyramid.settings import aslist
    from pyramid.tweens import EXCVIEW
    from pyramid.config import Configurator
    from typing import TYPE_CHECKING, Dict, Any, Callable, Tuple
    import wrapt

    from opentelemetry.semconv.trace import SpanAttributes
    from opentelemetry.trace import SpanKind

    from instana.log import logger
    from instana.singletons import tracer, agent
    from instana.util.secrets import strip_secrets_from_query
    from instana.util.traceutils import extract_custom_headers
    from instana.propagators.format import Format

    if TYPE_CHECKING:
        from pyramid.request import Request
        from pyramid.response import Response
        from pyramid.registry import Registry

    class InstanaTweenFactory(object):
        """A factory that provides Instana instrumentation tween for Pyramid apps"""

        def __init__(
            self, handler: Callable[["Request"], "Response"], registry: "Registry"
        ) -> None:
            self.handler = handler

        def __call__(self, request: "Request") -> "Response":
            ctx = tracer.extract(Format.HTTP_HEADERS, dict(request.headers))

            with tracer.start_as_current_span("wsgi", span_context=ctx) as span:
                span.set_attribute("http.host", request.host)
                span.set_attribute(SpanAttributes.HTTP_METHOD, request.method)
                span.set_attribute(SpanAttributes.HTTP_URL, request.path)

                extract_custom_headers(span, request.headers)

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
                        span.set_attribute(
                            "http.path_tpl", request.matched_route.pattern
                        )

                    extract_custom_headers(span, response.headers)

                    tracer.inject(span.context, Format.HTTP_HEADERS, response.headers)
                except HTTPException as e:
                    response = e
                    logger.debug(
                        "Pyramid InstanaTweenFactory HTTPException: ", exc_info=True
                    )
                except BaseException as e:
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
                    span.record_exception(e)

                    logger.debug(
                        "Pyramid InstanaTweenFactory BaseException: ", exc_info=True
                    )
                finally:
                    if response:
                        span.set_attribute(
                            SpanAttributes.HTTP_STATUS_CODE, response.status_int
                        )

                        if 500 <= response.status_int:
                            if response.exception:
                                span.record_exception(response.exception)
                            span.assure_errored()

                return response

    INSTANA_TWEEN = __name__ + ".InstanaTweenFactory"

    # implicit tween ordering
    def includeme(config: Configurator) -> None:
        logger.debug("Instrumenting pyramid")
        config.add_tween(INSTANA_TWEEN)

    # explicit tween ordering
    @wrapt.patch_function_wrapper("pyramid.config", "Configurator.__init__")
    def init_with_instana(
        wrapped: Callable[..., Configurator.__init__],
        instance: Configurator,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ):
        settings = kwargs.get("settings", {})
        tweens = aslist(settings.get("pyramid.tweens", []))

        if tweens and INSTANA_TWEEN not in settings:
            # pyramid.tweens.EXCVIEW is the name of built-in exception view provided by
            # pyramid.  We need our tween to be before it, otherwise unhandled
            # exceptions will be caught before they reach our tween.
            if EXCVIEW in tweens:
                tweens = [INSTANA_TWEEN] + tweens
            else:
                tweens = [INSTANA_TWEEN] + tweens + [EXCVIEW]
            settings["pyramid.tweens"] = "\n".join(tweens)
            kwargs["settings"] = settings

        if not kwargs.get("package", None):
            kwargs["package"] = caller_package()

        wrapped(*args, **kwargs)
        instance.include(__name__)

except ImportError:
    pass
