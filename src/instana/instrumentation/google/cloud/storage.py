# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import wrapt
import re

from typing import Any, Callable, Dict, Tuple, Union
from instana.log import logger
from instana.instrumentation.google.cloud.collectors import _storage_api
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

try:
    from google.cloud import storage

    logger.debug("Instrumenting google-cloud-storage")

    def _collect_attributes(
        api_request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract span tags from Google Cloud Storage API request. Returns None if the request is not
        supported.

        :param: dict
        :return: dict or None
        """
        method, path = api_request.get("method", None), api_request.get("path", None)

        if method not in _storage_api:
            return

        try:
            params = api_request.get("query_params", {})
            data = api_request.get("data", {})

            if path in _storage_api[method]:
                # check is any of string keys matches the path exactly
                return _storage_api[method][path](params, data)
            else:
                # look for a regex that matches the string
                for matcher, collect in _storage_api[method].items():
                    if not isinstance(matcher, re.Pattern):
                        continue

                    m = matcher.match(path)
                    if m is None:
                        continue

                    return collect(params, data, m)
        except Exception:
            logger.debug(
                "instana.instrumentation.google.cloud.storage._collect_attributes: ",
                exc_info=True,
            )

    def execute_with_instana(
        wrapped: Callable[..., object],
        instance: Union[storage.Batch, storage._http.Connection],
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        # batch requests are traced with finish_batch_with_instana()
        # also return early if we're not tracing
        if isinstance(instance, storage.Batch) or tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("gcs", span_context=parent_context) as span:
            try:
                attributes = _collect_attributes(kwargs)

                # don't trace if the call is not instrumented
                if attributes is None:
                    logger.debug(
                        f"uninstrumented Google Cloud Storage API request: {kwargs}"
                    )
                    return wrapped(*args, **kwargs)
                span.set_attributes(attributes)
                kv = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return kv

    def download_with_instana(
        wrapped: Callable[..., object],
        instance: storage.Blob,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        # return early if we're not tracing
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("gcs", span_context=parent_context) as span:
            span.set_attribute("gcs.op", "objects.get")
            span.set_attribute("gcs.bucket", instance.bucket.name)
            span.set_attribute("gcs.object", instance.name)

            start = len(args) > 4 and args[4] or kwargs.get("start", None)
            if start is None:
                start = ""

            end = len(args) > 5 and args[5] or kwargs.get("end", None)
            if end is None:
                end = ""

            if start != "" or end != "":
                span.set_attribute("gcs.range", "-".join((start, end)))

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
            else:
                return kv

    def upload_with_instana(
        wrapped: Callable[..., object],
        instance: storage.Blob,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        # return early if we're not tracing
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("gcs", span_context=parent_context) as span:
            span.set_attribute("gcs.op", "objects.insert")
            span.set_attribute("gcs.bucket", instance.bucket.name)
            span.set_attribute("gcs.object", instance.name)

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
            else:
                return kv

    def finish_batch_with_instana(
        wrapped: Callable[..., object],
        instance: storage.Batch,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        # return early if we're not tracing
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("gcs", span_context=parent_context) as span:
            span.set_attribute("gcs.op", "batch")
            span.set_attribute("gcs.projectId", instance._client.project)
            span.set_attribute("gcs.numberOfOperations", len(instance._requests))

            try:
                kv = wrapped(*args, **kwargs)
            except Exception as e:
                span.record_exception(e)
            else:
                return kv

    wrapt.wrap_function_wrapper(
        "google.cloud.storage._http", "Connection.api_request", execute_with_instana
    )
    wrapt.wrap_function_wrapper(
        "google.cloud.storage.blob", "Blob._do_download", download_with_instana
    )
    wrapt.wrap_function_wrapper(
        "google.cloud.storage.blob", "Blob._do_upload", upload_with_instana
    )
    wrapt.wrap_function_wrapper(
        "google.cloud.storage.batch", "Batch.finish", finish_batch_with_instana
    )
except ImportError:
    pass
