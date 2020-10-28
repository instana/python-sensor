from __future__ import absolute_import

import os
import time
import pytest
import requests
import multiprocessing
from tests.apps.fastapi_app import launch_fastapi
from instana.singletons import tracer
from ..helpers import testenv
from ..helpers import get_first_span_by_filter

@pytest.fixture(scope="module")
def server():
    import logging
    logger = multiprocessing.log_to_stderr()
    logger.setLevel(logging.WARN)

    # Override span queue with a multiprocessing version
    mp_queue = multiprocessing.Queue()
    tracer.recorder.agent.collector.span_queue = mp_queue
    logger.debug('Parent PID: %s', os.getpid())
    logger.debug('Parent mp_queue: %s', mp_queue)
    proc = multiprocessing.Process(target=launch_fastapi, args=(mp_queue,), daemon=True)
    proc.start()
    time.sleep(2)
    yield
    proc.kill() # Kill server after tests

def test_vanilla_get(server):
    result = requests.get(testenv["fastapi_server"] + '/')
    assert(result)
    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    # FastAPI instrumentation (like all instrumentation) _always_ traces unless told otherwise
    assert len(spans) == 1
    assert spans[0].n == 'asgi'

    assert "X-Instana-T" in result.headers
    assert "X-Instana-S" in result.headers
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers

def test_basic_get(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["fastapi_server"] + '/')

    assert(result)

    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "asgi"
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-Instana-T" in result.headers
    assert result.headers["X-Instana-T"] == asgi_span.t
    assert "X-Instana-S" in result.headers
    assert result.headers["X-Instana-S"] == asgi_span.s
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)

def test_path_templates(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["fastapi_server"] + '/users/1')

    assert(result)

    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "asgi"
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-Instana-T" in result.headers
    assert result.headers["X-Instana-T"] == asgi_span.t
    assert "X-Instana-S" in result.headers
    assert result.headers["X-Instana-S"] == asgi_span.s
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/users/1')
    assert(asgi_span.data['http']['path_tpl'] == '/users/{1}')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)

def test_secret_scrubbing(server):
    result = None
    with tracer.start_active_span('test'):
        result = requests.get(testenv["fastapi_server"] + '/?secret=shhh')

    assert(result)

    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "asgi"
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-Instana-T" in result.headers
    assert result.headers["X-Instana-T"] == asgi_span.t
    assert "X-Instana-S" in result.headers
    assert result.headers["X-Instana-S"] == asgi_span.s
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/')
    assert(asgi_span.data['http']['params'] == 'secret=<redacted>')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)

def test_synthetic_request(server):
    request_headers = {
        'X-Instana-Synthetic': '1'
    }
    with tracer.start_active_span('test'):
        result = requests.get(testenv["fastapi_server"] + '/', headers=request_headers)

    assert(result)

    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "asgi"
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-Instana-T" in result.headers
    assert result.headers["X-Instana-T"] == asgi_span.t
    assert "X-Instana-S" in result.headers
    assert result.headers["X-Instana-S"] == asgi_span.s
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)

    assert(asgi_span.sy)
    assert(urllib3_span.sy is None)
    assert(test_span.sy is None)

def test_custom_header_capture(server):
    from instana.singletons import agent

    # The background FastAPI server is pre-configured with custom headers to capture

    request_headers = {
        'X-Capture-This': 'this',
        'X-Capture-That': 'that'
    }
    with tracer.start_active_span('test'):
        result = requests.get(testenv["fastapi_server"] + '/', headers=request_headers)

    assert(result)

    time.sleep(3)
    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    span_filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, span_filter)
    assert(test_span)

    span_filter = lambda span: span.n == "urllib3"
    urllib3_span = get_first_span_by_filter(spans, span_filter)
    assert(urllib3_span)

    span_filter = lambda span: span.n == "asgi"
    asgi_span = get_first_span_by_filter(spans, span_filter)
    assert(asgi_span)

    assert(test_span.t == urllib3_span.t == asgi_span.t)
    assert(asgi_span.p == urllib3_span.s)
    assert(urllib3_span.p == test_span.s)

    assert "X-Instana-T" in result.headers
    assert result.headers["X-Instana-T"] == asgi_span.t
    assert "X-Instana-S" in result.headers
    assert result.headers["X-Instana-S"] == asgi_span.s
    assert "X-Instana-L" in result.headers
    assert result.headers["X-Instana-L"] == '1'
    assert "Server-Timing" in result.headers
    assert result.headers["Server-Timing"] == ("intid;desc=%s" % asgi_span.t)

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)

    assert("http.X-Capture-This" in asgi_span.data["custom"]['tags'])
    assert("this" == asgi_span.data["custom"]['tags']["http.X-Capture-This"])
    assert("http.X-Capture-That" in asgi_span.data["custom"]['tags'])
    assert("that" == asgi_span.data["custom"]['tags']["http.X-Capture-That"])
