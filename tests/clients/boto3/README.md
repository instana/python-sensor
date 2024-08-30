If you would like to run this test server manually from an ipython console:

```
import os
import urllib3

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from moto import mock_aws
import tests.apps.flask_app
from tests.helpers import testenv
from instana.singletons import tracer

http_client = urllib3.PoolManager()

@mock_aws
def test_app_boto3_sqs():
    with tracer.start_as_current_span("test") as span:
        span.set_attribute("span.kind", SpanKind.SERVER)
        span.set_attribute(SpanAttributes.HTTP_HOST, "localhost:80")
        span.set_attribute("http.path", "/")
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 200)
        response = http_client.request("GET", testenv["wsgi_server"] + "/boto3/sqs")

```
