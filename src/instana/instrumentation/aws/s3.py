# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

try:
    from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence, Type

    from instana.span_context import SpanContext

    if TYPE_CHECKING:
        from botocore.client import BaseClient
    import wrapt

    from instana.log import logger
    from instana.singletons import tracer
    from instana.util.traceutils import (
        get_tracer_tuple,
        tracing_is_off,
    )

    operations = {
        "upload_file": "UploadFile",
        "upload_fileobj": "UploadFileObj",
        "download_file": "DownloadFile",
        "download_fileobj": "DownloadFileObj",
    }

    def create_s3_span(
        wrapped: Callable[..., Dict[str, Any]],
        instance: Type["BaseClient"],
        args: Sequence[Dict[str, Any]],
        kwargs: Dict[str, Any],
        parent_context: SpanContext,
    ) -> None:
        with tracer.start_as_current_span("s3", span_context=parent_context) as span:
            try:
                span.set_attribute("s3.op", args[0])
                if "Bucket" in args[1].keys():
                    span.set_attribute("s3.bucket", args[1]["Bucket"])
            except Exception as exc:
                span.record_exception(exc)
                logger.debug("create_s3_span: collect error", exc_info=True)

    def collect_s3_injected_attributes(
        wrapped: Callable[..., object],
        instance: Type["BaseClient"],
        args: Sequence[object],
        kwargs: Dict[str, Any],
    ) -> Callable[..., object]:
        # If we're not tracing, just return
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span("s3", span_context=parent_context) as span:
            try:
                span.set_attribute("s3.op", operations[wrapped.__name__])
                if wrapped.__name__ in ["download_file", "download_fileobj"]:
                    span.set_attribute("s3.bucket", args[0])
                else:
                    span.set_attribute("s3.bucket", args[1])
                return wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
                logger.debug(
                    "collect_s3_injected_attributes: collect error", exc_info=True
                )

    for method in [
        "upload_file",
        "upload_fileobj",
        "download_file",
        "download_fileobj",
    ]:
        wrapt.wrap_function_wrapper(
            "boto3.s3.inject", method, collect_s3_injected_attributes
        )

    logger.debug("Instrumenting s3")
except ImportError:
    pass
