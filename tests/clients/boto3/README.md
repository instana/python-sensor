If you would like to run this test server manually from an ipython console:

```
import os
import urllib3

from moto import mock_aws
import tests.apps.flask_app
from tests.helpers import testenv
from instana.singletons import tracer

http_client = urllib3.PoolManager()

@mock_aws
def test_app_boto3_sqs():
    with tracer.start_active_span('wsgi') as scope:
        scope.span.set_tag('span.kind', 'entry')
        scope.span.set_tag('http.host', 'localhost:80')
        scope.span.set_tag('http.path', '/')
        scope.span.set_tag('http.method', 'GET')
        scope.span.set_tag('http.status_code', 200)
        response = http_client.request('GET', testenv["wsgi_server"] + '/boto3/sqs')

```
