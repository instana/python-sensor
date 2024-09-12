# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""
Module to handle the work related to the many AWS Lambda Triggers.
"""

import base64
import gzip
import json
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from opentelemetry.semconv.trace import SpanAttributes

from instana.log import logger
from instana.propagators.format import Format

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from instana.agent.aws_lambda import AWSLambdaAgent
    from instana.span.span import InstanaSpan
    from instana.tracer import InstanaTracer

STR_LAMBDA_TRIGGER = "lambda.trigger"


def get_context(tracer: "InstanaTracer", event: Dict[str, Any]) -> Optional["Context"]:
    # TODO: Search for more types of trigger context
    is_proxy_event = (
        is_api_gateway_proxy_trigger(event)
        or is_api_gateway_v2_proxy_trigger(event)
        or is_application_load_balancer_trigger(event)
    )

    if is_proxy_event:
        return tracer.extract(
            Format.HTTP_HEADERS,
            event.get("headers", {}),
            disable_w3c_trace_context=True,
        )

    return tracer.extract(Format.HTTP_HEADERS, event, disable_w3c_trace_context=True)


def is_api_gateway_proxy_trigger(event: Dict[str, Any]) -> bool:
    for key in ["resource", "path", "httpMethod"]:
        if key not in event:
            return False
    return True


def is_api_gateway_v2_proxy_trigger(event: Dict[str, Any]) -> bool:
    for key in ["version", "requestContext"]:
        if key not in event:
            return False

    if event["version"] != "2.0":
        return False

    for key in ["apiId", "stage", "http"]:
        if key not in event["requestContext"]:
            return False

    return True


def is_application_load_balancer_trigger(event: Dict[str, Any]) -> bool:
    if "requestContext" in event and "elb" in event["requestContext"]:
        return True
    return False


def is_cloudwatch_trigger(event: Dict[str, Any]) -> bool:
    if "source" in event and "detail-type" in event:
        if (
            event["source"] == "aws.events"
            and event["detail-type"] == "Scheduled Event"
        ):
            return True
    return False


def is_cloudwatch_logs_trigger(event: Dict[str, Any]) -> bool:
    if hasattr(event, "get") and event.get("awslogs", "\b") != "\b":
        return True
    else:
        return False


def is_s3_trigger(event: Dict[str, Any]) -> bool:
    if "Records" in event:
        if len(event["Records"]) > 0 and event["Records"][0]["eventSource"] == "aws:s3":
            return True
    return False


def is_sqs_trigger(event: Dict[str, Any]) -> bool:
    if "Records" in event:
        if (
            len(event["Records"]) > 0
            and event["Records"][0]["eventSource"] == "aws:sqs"
        ):
            return True
    return False


def read_http_query_params(event: Dict[str, Any]) -> str:
    """
    Used to parse the Lambda QueryString formats.

    @param event: lambda event dict
    @return: String in the form of "a=b&c=d"
    """
    params = []
    try:
        if event is None or type(event) is not dict:
            return ""

        mvqsp = event.get("multiValueQueryStringParameters", None)
        qsp = event.get("queryStringParameters", None)

        if mvqsp is not None and type(mvqsp) is dict:
            for key in mvqsp:
                params.append(f"{key}={mvqsp[key]}")
            return "&".join(params)
        elif qsp is not None and type(qsp) is dict:
            for key in qsp:
                params.append(f"{key}={qsp[key]}")
            return "&".join(params)
        else:
            return ""
    except Exception:
        logger.debug("AWS Lambda read_http_query_params error: ", exc_info=True)
        return ""


def capture_extra_headers(
    event: Dict[str, Any], span: "InstanaSpan", extra_headers: List[Dict[str, Any]]
) -> None:
    """
    Capture the headers specified in `extra_headers` from `event` and log them
    as a tag in the span.

    @param event: the lambda event
    @param span: the lambda entry span
    @param extra_headers: a list of http headers to capture
    @return: None
    """
    try:
        event_headers = event.get("headers", None)

        if event_headers:
            for custom_header in extra_headers:
                for key in event_headers:
                    if key.lower() == custom_header.lower():
                        span.set_attribute(
                            "http.header.%s" % custom_header, event_headers[key]
                        )
    except Exception:
        logger.debug("AWS Lambda capture_extra_headers error: ", exc_info=True)


def enrich_lambda_span(
    agent: "AWSLambdaAgent",
    span: "InstanaSpan",
    event: Optional[Dict[str, Any]],
    context: "Context",
) -> None:
    """
    Extract the required information about this Lambda run (and the trigger) and store the data
    on `span`.

    @param agent: the AWSLambdaAgent in use
    @param span: the Lambda entry span
    @param event: the lambda handler event
    @param context: the lambda handler context
    @return: None
    """
    try:
        span.set_attribute("lambda.arn", agent.collector.get_fq_arn())
        span.set_attribute("lambda.name", context.function_name)
        span.set_attribute("lambda.version", context.function_version)

        if not event or not isinstance(event, dict):
            logger.debug(f"AWS Lambda enrich_lambda_span: bad event {type(event)}")
            return

        if is_api_gateway_proxy_trigger(event):
            logger.debug("Detected as API Gateway Proxy Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:api.gateway")
            span.set_attribute(SpanAttributes.HTTP_METHOD, event["httpMethod"])
            span.set_attribute(SpanAttributes.HTTP_URL, event["path"])
            span.set_attribute("http.path_tpl", event["resource"])
            span.set_attribute("http.params", read_http_query_params(event))

            if agent.options.extra_http_headers:
                capture_extra_headers(event, span, agent.options.extra_http_headers)

        elif is_api_gateway_v2_proxy_trigger(event):
            logger.debug("Detected as API Gateway v2.0 Proxy Trigger")

            reqCtx = event["requestContext"]

            # trim optional HTTP method prefix
            route_path = event["routeKey"].split(" ", 2)[-1]

            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:api.gateway")
            span.set_attribute(SpanAttributes.HTTP_METHOD, reqCtx["http"]["method"])
            span.set_attribute(SpanAttributes.HTTP_URL, reqCtx["http"]["path"])
            span.set_attribute("http.path_tpl", route_path)
            span.set_attribute("http.params", read_http_query_params(event))

            if agent.options.extra_http_headers:
                capture_extra_headers(event, span, agent.options.extra_http_headers)

        elif is_application_load_balancer_trigger(event):
            logger.debug("Detected as Application Load Balancer Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:application.load.balancer")
            span.set_attribute(SpanAttributes.HTTP_METHOD, event["httpMethod"])
            span.set_attribute(SpanAttributes.HTTP_URL, event["path"])
            span.set_attribute("http.params", read_http_query_params(event))

            if agent.options.extra_http_headers:
                capture_extra_headers(event, span, agent.options.extra_http_headers)

        elif is_cloudwatch_trigger(event):
            logger.debug("Detected as Cloudwatch Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:cloudwatch.events")
            span.set_attribute("data.lambda.cw.events.id", event["id"])

            resources = event["resources"]
            if len(event["resources"]) > 3:
                resources = event["resources"][:3]
                span.set_attribute("lambda.cw.events.more", True)
            else:
                span.set_attribute("lambda.cw.events.more", False)

            report = []
            for item in resources:
                if len(item) > 200:
                    item = item[:200]
                report.append(item)
            span.set_attribute("lambda.cw.events.resources", report)

        elif is_cloudwatch_logs_trigger(event):
            logger.debug("Detected as Cloudwatch Logs Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:cloudwatch.logs")

            try:
                if "awslogs" in event and "data" in event["awslogs"]:
                    data = event["awslogs"]["data"]
                    decoded_data = base64.b64decode(data)
                    decompressed_data = gzip.GzipFile(
                        fileobj=BytesIO(decoded_data)
                    ).read()
                    log_data = json.loads(decompressed_data.decode("utf-8"))

                    span.set_attribute(
                        "lambda.cw.logs.group", log_data.get("logGroup", None)
                    )
                    span.set_attribute(
                        "lambda.cw.logs.stream", log_data.get("logStream", None)
                    )
                    if len(log_data["logEvents"]) > 3:
                        span.set_attribute("lambda.cw.logs.more", True)
                        events = log_data["logEvents"][:3]
                    else:
                        events = log_data["logEvents"]

                    event_data = []
                    for item in events:
                        msg = item.get("message", None)
                        if len(msg) > 200:
                            msg = msg[:200]
                        event_data.append(msg)
                    span.set_attribute("lambda.cw.logs.events", event_data)
            except Exception as e:
                span.set_attribute("lambda.cw.logs.decodingError", repr(e))
        elif is_s3_trigger(event):
            logger.debug("Detected as S3 Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:s3")

            if "Records" in event:
                events = []
                for item in event["Records"][:3]:
                    bucket_name = "Unknown"
                    if "s3" in item and "bucket" in item["s3"]:
                        bucket_name = item["s3"]["bucket"]["name"]

                    object_name = ""
                    if "s3" in item and "object" in item["s3"]:
                        object_name = item["s3"]["object"].get("key", "Unknown")

                    if len(object_name) > 200:
                        object_name = object_name[:200]

                    events.append(
                        {
                            "event": item["eventName"],
                            "bucket": bucket_name,
                            "object": object_name,
                        }
                    )
                span.set_attribute("lambda.s3.events", events)

        elif is_sqs_trigger(event):
            logger.debug("Detected as SQS Trigger")
            span.set_attribute(STR_LAMBDA_TRIGGER, "aws:sqs")

            if "Records" in event:
                events = []
                for item in event["Records"][:3]:
                    events.append({"queue": item["eventSourceARN"]})
                span.set_attribute("lambda.sqs.messages", events)
        else:
            logger.debug(f"Detected as Unknown Trigger: {event}")
            span.set_attribute(STR_LAMBDA_TRIGGER, "unknown")

    except Exception:
        logger.debug("AWS Lambda enrich_lambda_span error: ", exc_info=True)
