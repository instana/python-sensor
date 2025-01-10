# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017


from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple, Union

import wrapt
from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import agent
from instana.util.secrets import strip_secrets_from_query
from instana.util.traceutils import get_tracer_tuple, tracing_is_off, extract_custom_headers

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

try:
    import urllib3

    def _collect_kvs(
        instance: Union[
            urllib3.connectionpool.HTTPConnectionPool,
            urllib3.connectionpool.HTTPSConnectionPool,
        ],
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        kvs = dict()
        try:
            kvs["host"] = instance.host
            kvs["port"] = instance.port

            if args and len(args) == 2:
                kvs["method"] = args[0]
                kvs["path"] = args[1]
            else:
                kvs["method"] = kwargs.get("method")
                kvs["path"] = (
                    kwargs.get("path") if kwargs.get("path") else kwargs.get("url")
                )

            # Strip any secrets from potential query params
            if kvs.get("path") and ("?" in kvs["path"]):
                parts = kvs["path"].split("?")
                kvs["path"] = parts[0]
                if len(parts) == 2:
                    kvs["query"] = strip_secrets_from_query(
                        parts[1],
                        agent.options.secrets_matcher,
                        agent.options.secrets_list,
                    )

            url = kvs["host"] + ":" + str(kvs["port"]) + kvs["path"]
            if isinstance(instance, urllib3.connectionpool.HTTPSConnectionPool):
                kvs["url"] = f"https://{url}"
            else:
                kvs["url"] = f"http://{url}"
        except Exception:
            logger.debug("urllib3 _collect_kvs error: ", exc_info=True)
            return kvs
        else:
            return kvs

    def collect_response(
        span: "InstanaSpan", response: urllib3.response.HTTPResponse
    ) -> None:
        try:
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, response.status)

            extract_custom_headers(span, response.headers)

            if 500 <= response.status:
                span.mark_as_errored()
        except Exception:
            logger.debug("urllib3 collect_response error: ", exc_info=True)

    @wrapt.patch_function_wrapper("urllib3", "HTTPConnectionPool.urlopen")
    def urlopen_with_instana(
        wrapped: Callable[
            ..., Union[urllib3.HTTPConnectionPool, urllib3.HTTPSConnectionPool]
        ],
        instance: Union[
            urllib3.connectionpool.HTTPConnectionPool,
            urllib3.connectionpool.HTTPSConnectionPool,
        ],
        args: Tuple[int, str, Tuple[Any, ...]],
        kwargs: Dict[str, Any],
    ) -> urllib3.response.HTTPResponse:
        tracer, parent_span, span_name = get_tracer_tuple()

        # If we're not tracing, just return; boto3 has it's own visibility
        if tracing_is_off() or (span_name == "boto3"):
            return wrapped(*args, **kwargs)

        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "urllib3", span_context=parent_context
        ) as span:
            try:
                kvs = _collect_kvs(instance, args, kwargs)
                if "url" in kvs:
                    span.set_attribute(SpanAttributes.HTTP_URL, kvs["url"])
                if "query" in kvs:
                    span.set_attribute("http.params", kvs["query"])
                if "method" in kvs:
                    span.set_attribute(SpanAttributes.HTTP_METHOD, kvs["method"])
                if "headers" in kwargs:
                    extract_custom_headers(span, kwargs["headers"])
                    tracer.inject(span.context, Format.HTTP_HEADERS, kwargs["headers"])

                response = wrapped(*args, **kwargs)

                collect_response(span, response)

                return response
            except Exception as e:
                span.record_exception(e)
                raise

    logger.debug("Instrumenting urllib3")
except ImportError:
    pass
