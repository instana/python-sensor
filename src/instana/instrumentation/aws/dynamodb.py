# (c) Copyright IBM Corp. 2025

from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence, Type

if TYPE_CHECKING:
    from botocore.client import BaseClient

from instana.log import logger
from instana.singletons import tracer
from instana.span_context import SpanContext


def create_dynamodb_span(
    wrapped: Callable[..., Dict[str, Any]],
    instance: Type["BaseClient"],
    args: Sequence[Dict[str, Any]],
    kwargs: Dict[str, Any],
    parent_context: SpanContext,
) -> None:
    with tracer.start_as_current_span("dynamodb", span_context=parent_context) as span:
        try:
            span.set_attribute("dynamodb.op", args[0])
            span.set_attribute("dynamodb.region", instance._client_config.region_name)
            if "TableName" in args[1].keys():
                span.set_attribute("dynamodb.table", args[1]["TableName"])
        except Exception as exc:
            span.record_exception(exc)
            logger.debug("create_dynamodb_span: collect error", exc_info=True)


logger.debug("Instrumenting DynamoDB")
