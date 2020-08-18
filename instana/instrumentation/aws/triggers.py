"""
Module to handle the work related to the many AWS Lambda Triggers.
"""
import gzip
import json
import base64
from io import BytesIO

from ...log import logger


def get_context(tracer, event):
    # TODO: Search for more types of trigger context
    if is_api_gateway_proxy_trigger(event) or is_application_load_balancer_trigger(event):
        return tracer.extract('http_headers', event['headers'])

    return tracer.extract('http_headers', event)


def is_api_gateway_proxy_trigger(event):
    for key in ["resource", "path", "httpMethod"]:
        if key not in event:
            return False
    return True


def is_application_load_balancer_trigger(event):
    if 'requestContext' in event and 'elb' in event['requestContext']:
        return True
    return False


def is_cloudwatch_trigger(event):
    if "source" in event and 'detail-type' in event:
        if event["source"] == 'aws.events' and event['detail-type'] == 'Scheduled Event':
            return True
    return False


def is_cloudwatch_logs_trigger(event):
    if hasattr(event, 'get') and event.get("awslogs", False) is not False:
        return True
    else:
        return False


def is_s3_trigger(event):
    if "Records" in event:
        if len(event["Records"]) > 0 and event["Records"][0]["eventSource"] == 'aws:s3':
            return True
    return False


def is_sqs_trigger(event):
    if "Records" in event:
        if len(event["Records"]) > 0 and event["Records"][0]["eventSource"] == 'aws:sqs':
            return True
    return False


def read_http_query_params(event):
    """
    Used to parse the Lambda QueryString formats.

    @param event: lambda event dict
    @return: String in the form of "a=b&c=d"
    """
    params = []
    try:
        if event is None or type(event) is not dict:
            return ""

        mvqsp = event.get('multiValueQueryStringParameters', None)
        qsp = event.get('queryStringParameters', None)

        if mvqsp is not None and type(mvqsp) is dict:
            for key in mvqsp:
                params.append("%s=%s" % (key, mvqsp[key]))
            return "&".join(params)
        elif qsp is not None and type(qsp) is dict:
            for key in qsp:
                params.append("%s=%s" % (key, qsp[key]))
            return "&".join(params)
        else:
            return ""
    except:
        logger.debug("read_http_query_params: ", exc_info=True)
        return ""


def capture_extra_headers(event, span, extra_headers):
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

        if event_headers is not None:
            for custom_header in extra_headers:
                for key in event_headers:
                    if key.lower() == custom_header.lower():
                        span.set_tag("http.%s" % custom_header, event_headers[key])
    except:
        logger.debug("capture_extra_headers: ", exc_info=True)


def enrich_lambda_span(agent, span, event, context):
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
        span.set_tag('lambda.arn', agent.collector.get_fq_arn())
        span.set_tag('lambda.name', context.function_name)
        span.set_tag('lambda.version', context.function_version)

        if event is None or type(event) is not dict:
            logger.debug("enrich_lambda_span: bad event %s", type(event))
            return

        if is_api_gateway_proxy_trigger(event):
            span.set_tag('lambda.trigger', 'aws:api.gateway')
            span.set_tag('http.method', event["httpMethod"])
            span.set_tag('http.url', event["path"])
            span.set_tag('http.path_tpl', event["resource"])
            span.set_tag('http.params', read_http_query_params(event))

            if agent.options.extra_http_headers is not None:
                capture_extra_headers(event, span, agent.options.extra_http_headers)

        elif is_application_load_balancer_trigger(event):
            span.set_tag('lambda.trigger', 'aws:application.load.balancer')
            span.set_tag('http.method', event["httpMethod"])
            span.set_tag('http.url', event["path"])
            span.set_tag('http.params', read_http_query_params(event))

            if agent.options.extra_http_headers is not None:
                capture_extra_headers(event, span, agent.options.extra_http_headers)

        elif is_cloudwatch_trigger(event):
            span.set_tag('lambda.trigger', 'aws:cloudwatch.events')
            span.set_tag('data.lambda.cw.events.id', event['id'])

            resources = event['resources']
            resource_count = len(event['resources'])
            if resource_count > 3:
                resources = event['resources'][:3]
                span.set_tag('lambda.cw.events.more', True)
            else:
                span.set_tag('lambda.cw.events.more', False)

            report = []
            for item in resources:
                if len(item) > 200:
                    item = item[:200]
                report.append(item)
            span.set_tag('lambda.cw.events.resources', report)

        elif is_cloudwatch_logs_trigger(event):
            span.set_tag('lambda.trigger', 'aws:cloudwatch.logs')

            try:
                if 'awslogs' in event and 'data' in event['awslogs']:
                    data = event['awslogs']['data']
                    decoded_data = base64.b64decode(data)
                    decompressed_data = gzip.GzipFile(fileobj=BytesIO(decoded_data)).read()
                    log_data = json.loads(decompressed_data.decode('utf-8'))

                    span.set_tag('lambda.cw.logs.group', log_data.get('logGroup', None))
                    span.set_tag('lambda.cw.logs.stream', log_data.get('logStream', None))
                    if len(log_data['logEvents']) > 3:
                        span.set_tag('lambda.cw.logs.more', True)
                        events = log_data['logEvents'][:3]
                    else:
                        events = log_data['logEvents']

                    event_data = []
                    for item in events:
                        msg = item.get('message', None)
                        if len(msg) > 200:
                            msg = msg[:200]
                        event_data.append(msg)
                    span.set_tag('lambda.cw.logs.events', event_data)
            except Exception as e:
                span.set_tag('lambda.cw.logs.decodingError', repr(e))
        elif is_s3_trigger(event):
            span.set_tag('lambda.trigger', 'aws:s3')

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

                    events.append({"event": item['eventName'],
                                   "bucket": bucket_name,
                                   "object": object_name})
                span.set_tag('lambda.s3.events', events)

        elif is_sqs_trigger(event):
            span.set_tag('lambda.trigger', 'aws:sqs')

            if "Records" in event:
                events = []
                for item in event["Records"][:3]:
                    events.append({'queue': item['eventSourceARN']})
                span.set_tag('lambda.sqs.messages', events)
    except:
        logger.debug("enrich_lambda_span: ", exc_info=True)
