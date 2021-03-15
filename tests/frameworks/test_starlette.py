# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import time
import pytest
import requests
import multiprocessing
from ..helpers import testenv
from instana.singletons import tracer
from ..helpers import get_first_span_by_filter

@pytest.fixture(scope="module")
def server():
    from tests.apps.starlette_app import launch_starlette
    proc = multiprocessing.Process(target=launch_starlette, args=(), daemon=True)
    proc.start()
    time.sleep(2)
    yield
    proc.kill() # Kill server after tests

def test_vanilla_get(server):
    result = requests.get(testenv["starlette_server"] + '/')
    assert(result)
    spans = tracer.recorder.queued_spans()
    # Starlette instrumentation (like all instrumentation) _always_ traces unless told otherwise
    assert len(spans) == 1
    assert spans[0].n == 'sdk'

    assert "X-INSTANA-T" in result.headers
    assert "X-INSTANA-S" in result.headers
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers

def test_basic_get(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["starlette_server"] + '/')

    assert(result)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-INSTANA-T" in result.headers
    assert result.headers["X-INSTANA-T"] == asgi_span.t
    assert "X-INSTANA-S" in result.headers
    assert result.headers["X-INSTANA-S"] == asgi_span.s
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert(asgi_span.ec == None)
    assert(asgi_span.data['sdk']['custom']['tags']['http.host'] == '127.0.0.1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.method'] == 'GET')
    assert(asgi_span.data['sdk']['custom']['tags']['http.status_code'] == 200)
    assert('http.error' not in asgi_span.data['sdk']['custom']['tags'])
    assert('http.params' not in asgi_span.data['sdk']['custom']['tags'])

def test_path_templates(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["starlette_server"] + '/users/1')

    assert(result)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-INSTANA-T" in result.headers
    assert result.headers["X-INSTANA-T"] == asgi_span.t
    assert "X-INSTANA-S" in result.headers
    assert result.headers["X-INSTANA-S"] == asgi_span.s
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert(asgi_span.ec == None)
    assert(asgi_span.data['sdk']['custom']['tags']['http.host'] == '127.0.0.1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path'] == '/users/1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'] == '/users/{user_id}')
    assert(asgi_span.data['sdk']['custom']['tags']['http.method'] == 'GET')
    assert(asgi_span.data['sdk']['custom']['tags']['http.status_code'] == 200)
    assert('http.error' not in asgi_span.data['sdk']['custom']['tags'])
    assert('http.params' not in asgi_span.data['sdk']['custom']['tags'])

def test_secret_scrubbing(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["starlette_server"] + '/?secret=shhh')

    assert(result)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-INSTANA-T" in result.headers
    assert result.headers["X-INSTANA-T"] == asgi_span.t
    assert "X-INSTANA-S" in result.headers
    assert result.headers["X-INSTANA-S"] == asgi_span.s
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert(asgi_span.ec == None)
    assert(asgi_span.data['sdk']['custom']['tags']['http.host'] == '127.0.0.1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.method'] == 'GET')
    assert(asgi_span.data['sdk']['custom']['tags']['http.params'] == 'secret=<redacted>')
    assert(asgi_span.data['sdk']['custom']['tags']['http.status_code'] == 200)
    assert('http.error' not in asgi_span.data['sdk']['custom']['tags'])

def test_synthetic_request(server):
    request_headers = {
        'X-INSTANA-SYNTHETIC': '1'
    }
    with tracer.start_active_span('test'):
        result = requests.get(testenv["starlette_server"] + '/', headers=request_headers)

    assert(result)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-INSTANA-T" in result.headers
    assert result.headers["X-INSTANA-T"] == asgi_span.t
    assert "X-INSTANA-S" in result.headers
    assert result.headers["X-INSTANA-S"] == asgi_span.s
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert(asgi_span.ec == None)
    assert(asgi_span.data['sdk']['custom']['tags']['http.host'] == '127.0.0.1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.method'] == 'GET')
    assert(asgi_span.data['sdk']['custom']['tags']['http.status_code'] == 200)
    assert('http.error' not in asgi_span.data['sdk']['custom']['tags'])
    assert('http.params' not in asgi_span.data['sdk']['custom']['tags'])

    assert(asgi_span.sy)
    assert(urllib3_span.sy is None)
    assert(test_span.sy is None)

def test_custom_header_capture(server):
    from instana.singletons import agent

    # The background Starlette server is pre-configured with custom headers to capture

    request_headers = {
        'X-Capture-This': 'this',
        'X-Capture-That': 'that'
    }
    with tracer.start_active_span('test'):
        result = requests.get(testenv["starlette_server"] + '/', headers=request_headers)

    assert(result)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'test'
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "sdk" and span.data['sdk']['name'] == 'asgi'
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-INSTANA-T" in result.headers
    assert result.headers["X-INSTANA-T"] == asgi_span.t
    assert "X-INSTANA-S" in result.headers
    assert result.headers["X-INSTANA-S"] == asgi_span.s
    assert "X-INSTANA-L" in result.headers
    assert result.headers["X-INSTANA-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert(asgi_span.ec == None)
    assert(asgi_span.data['sdk']['custom']['tags']['http.host'] == '127.0.0.1')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.path_tpl'] == '/')
    assert(asgi_span.data['sdk']['custom']['tags']['http.method'] == 'GET')
    assert(asgi_span.data['sdk']['custom']['tags']['http.status_code'] == 200)
    assert('http.error' not in asgi_span.data['sdk']['custom']['tags'])
    assert('http.params' not in asgi_span.data['sdk']['custom']['tags'])

    assert("http.header.X-Capture-This" in asgi_span.data["sdk"]["custom"]['tags'])
    assert("this" == asgi_span.data["sdk"]["custom"]['tags']["http.header.X-Capture-This"])
    assert("http.header.X-Capture-That" in asgi_span.data["sdk"]["custom"]['tags'])
    assert("that" == asgi_span.data["sdk"]["custom"]['tags']["http.header.X-Capture-That"])
