# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import urllib3
import pytest
from typing import Generator

from instana.util.ids import hex_id
from tests.apps import bottle_app
from tests.helpers import testenv
from instana.singletons import agent, tracer
from instana.span.span import get_current_span


class TestWSGI:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        time.sleep(0.1)

    def test_vanilla_requests(self) -> None:
        response = self.http.request('GET', testenv["wsgi_server"] + '/')
        spans = self.recorder.queued_spans()

        assert 1 == len(spans)
        assert get_current_span().is_recording() is False
        assert response.status == 200

    def test_get_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/')

        spans = self.recorder.queued_spans()

        assert 3 == len(spans)
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        assert wsgi_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert '127.0.0.1:' + str(testenv["wsgi_port"]) == wsgi_span.data["http"]["host"]
        assert '/' == wsgi_span.data["http"]["path"]
        assert 'GET' == wsgi_span.data["http"]["method"]
        assert "200" == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

    def test_synthetic_request(self) -> None:
        headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()

        assert 3 == len(spans)
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert wsgi_span.sy
        assert urllib3_span.sy is None
        assert test_span.sy is None


    def test_custom_header_capture(self) -> None:
        # Hack together a manual custom headers list
        agent.options.extra_http_headers = [u'X-Capture-This', u'X-Capture-That']

        request_headers = {}
        request_headers['X-Capture-This'] = 'this'
        request_headers['X-Capture-That'] = 'that'

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        spans = self.recorder.queued_spans()

        assert 3 == len(spans)
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert '127.0.0.1:' + str(testenv["wsgi_port"]) == wsgi_span.data["http"]["host"]
        assert '/' == wsgi_span.data["http"]["path"]
        assert 'GET' == wsgi_span.data["http"]["method"]
        assert "200" == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        assert "X-Capture-This" in wsgi_span.data["http"]["header"]
        assert "this" == wsgi_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in wsgi_span.data["http"]["header"]
        assert "that" == wsgi_span.data["http"]["header"]["X-Capture-That"]

    def test_secret_scrubbing(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/?secret=shhh')

        spans = self.recorder.queued_spans()

        assert 3 == len(spans)
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert '127.0.0.1:' + str(testenv["wsgi_port"]) == wsgi_span.data["http"]["host"]
        assert '/' == wsgi_span.data["http"]["path"]
        assert 'secret=<redacted>' == wsgi_span.data["http"]["params"]
        assert 'GET' == wsgi_span.data["http"]["method"]
        assert "200" == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

    def test_with_incoming_context(self) -> None:
        request_headers = dict()
        request_headers['X-INSTANA-T'] = '0000000000000001'
        request_headers['X-INSTANA-S'] = '0000000000000001'

        response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        wsgi_span = spans[0]

        # assert wsgi_span.t == '0000000000000001'
        # assert wsgi_span.p == '0000000000000001'
        assert wsgi_span.t == 1
        assert wsgi_span.p == 1

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value

    def test_with_incoming_mixed_case_context(self) -> None:
        request_headers = dict()
        request_headers['X-InSTANa-T'] = '0000000000000001'
        request_headers['X-instana-S'] = '0000000000000001'

        response = self.http.request('GET', testenv["wsgi_server"] + '/', headers=request_headers)

        assert response
        assert 200 == response.status

        spans = self.recorder.queued_spans()
        assert 1 == len(spans)

        wsgi_span = spans[0]

        # assert wsgi_span.t == '0000000000000001'
        # assert wsgi_span.p == '0000000000000001'
        assert wsgi_span.t == 1
        assert wsgi_span.p == 1

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value

    def test_response_headers(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["wsgi_server"] + '/')

        spans = self.recorder.queued_spans()

        assert 3 == len(spans)
        assert get_current_span().is_recording() is False

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 200 == response.status

        assert 'X-INSTANA-T' in response.headers
        assert int(response.headers['X-INSTANA-T'], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert 'X-INSTANA-S' in response.headers
        assert int(response.headers['X-INSTANA-S'], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert 'X-INSTANA-L' in response.headers
        assert response.headers['X-INSTANA-L'] == '1'

        assert 'Server-Timing' in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers['Server-Timing'] == server_timing_value
