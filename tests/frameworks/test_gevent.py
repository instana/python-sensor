# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import pytest

import urllib3
import gevent
from gevent.pool import Group
from typing import Generator

import tests.apps.flask_app
from instana.singletons import tracer
from tests.helpers import testenv, get_spans_by_filter, filter_test_span


# Skip the tests if the environment variable `GEVENT_TEST` is not set
pytestmark = pytest.mark.skipif(not os.environ.get("GEVENT_TEST"), reason="GEVENT_TEST not set")


class TestGEvent:
    @classmethod
    def setup_class(cls) -> None:
        """Setup that runs once before all tests in the class"""
        cls.http = urllib3.HTTPConnectionPool('127.0.0.1', port=testenv["flask_port"], maxsize=20)
        cls.recorder = tracer.span_processor

    @pytest.fixture(autouse=True)
    def setUp(self) -> Generator[None, None, None]:
        """Clear all spans before each test run"""
        self.recorder.clear_spans()

    def make_http_call(self, n=None):
        """Helper function to make HTTP calls"""
        return self.http.request('GET', testenv["flask_server"] + '/')

    def spawn_calls(self):
        """Helper function to spawn multiple HTTP calls"""
        with tracer.start_as_current_span('spawn_calls'):
            jobs = []
            jobs.append(gevent.spawn(self.make_http_call))
            jobs.append(gevent.spawn(self.make_http_call))
            jobs.append(gevent.spawn(self.make_http_call))
            gevent.joinall(jobs, timeout=2)

    def spawn_imap_unordered(self):
        """Helper function to test imap_unordered"""
        igroup = Group()
        result = []
        with tracer.start_as_current_span('test'):
            for i in igroup.imap_unordered(self.make_http_call, range(3)):
                result.append(i)

    def launch_gevent_chain(self):
        """Helper function to launch a chain of gevent calls"""
        with tracer.start_as_current_span('test'):
            gevent.spawn(self.spawn_calls).join()

    def test_spawning(self):
        gevent.spawn(self.launch_gevent_chain)
        gevent.sleep(2)
        
        spans = self.recorder.queued_spans()
        
        assert len(spans) == 8
        
        test_spans = get_spans_by_filter(spans, filter_test_span)
        assert test_spans
        assert len(test_spans) == 1
        
        test_span = test_spans[0]
        
        span_filter = lambda span: span.n == "sdk" \
                                  and span.data['sdk']['name'] == 'spawn_calls' and span.p == test_span.s
        spawn_spans = get_spans_by_filter(spans, span_filter)
        assert spawn_spans
        assert len(spawn_spans) == 1
        
        spawn_span = spawn_spans[0]
        
        span_filter = lambda span: span.n == "urllib3"
        urllib3_spans = get_spans_by_filter(spans, span_filter)
        
        for urllib3_span in urllib3_spans:
            # spans should all have the same test span parent
            assert urllib3_span.t == spawn_span.t
            assert urllib3_span.p == spawn_span.s
            
            # find the wsgi span generated from this urllib3 request
            span_filter = lambda span: span.n == "wsgi" and span.p == urllib3_span.s
            wsgi_spans = get_spans_by_filter(spans, span_filter)
            assert wsgi_spans is not None
            assert len(wsgi_spans) == 1

    def test_imap_unordered(self):
        gevent.spawn(self.spawn_imap_unordered)
        gevent.sleep(2)
        
        spans = self.recorder.queued_spans()
        assert len(spans) == 7
        
        test_spans = get_spans_by_filter(spans, filter_test_span)
        assert test_spans is not None
        assert len(test_spans) == 1
        
        test_span = test_spans[0]
        
        span_filter = lambda span: span.n == "urllib3"
        urllib3_spans = get_spans_by_filter(spans, span_filter)
        assert len(urllib3_spans) == 3
        
        for urllib3_span in urllib3_spans:
            # spans should all have the same test span parent
            assert urllib3_span.t == test_span.t
            assert urllib3_span.p == test_span.s
            
            # find the wsgi span generated from this urllib3 request
            span_filter = lambda span: span.n == "wsgi" and span.p == urllib3_span.s
            wsgi_spans = get_spans_by_filter(spans, span_filter)
            assert wsgi_spans is not None
            assert len(wsgi_spans) == 1
