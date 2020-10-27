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
    time.sleep(1)
    yield
    proc.kill() # Kill server after tests

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

    assert('http' in asgi_span.data)
    assert(asgi_span.ec == None)
    assert(isinstance(asgi_span.stack, list))
    assert(asgi_span.data['http']['host'] == '127.0.0.1')
    assert(asgi_span.data['http']['path'] == '/')
    assert(asgi_span.data['http']['method'] == 'GET')
    assert(asgi_span.data['http']['status'] == 200)
    assert(asgi_span.data['http']['error'] == None)
