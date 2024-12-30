# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import unittest
import urllib3
import flask
from unittest.mock import patch

from instana.util.ids import hex_id

if hasattr(flask.signals, 'signals_available'):
    from flask.signals import signals_available
else:
    # Beginning from 2.3.0 as stated in the notes
    # https://flask.palletsprojects.com/en/2.3.x/changes/#version-2-3-0
    # "Signals are always available. blinker>=1.6.2 is a required dependency.
    # The signals_available attribute is deprecated. #5056"
    signals_available = True

from opentelemetry.trace import SpanKind

import tests.apps.flask_app
from instana.singletons import tracer, agent
from instana.span.span import get_current_span
from tests.helpers import testenv


class TestFlask(unittest.TestCase):

    def setUp(self) -> None:
        """ Clear all spans before a test run """
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

    def tearDown(self) -> None:
        """ Do nothing for now """
        return None

    def test_vanilla_requests(self) -> None:
        r = self.http.request('GET', testenv["flask_server"] + '/')
        assert r.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    def test_get_request(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request("GET", testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Synthetic
        assert wsgi_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert "/" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_get_request_with_query_params(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["flask_server"] + "/" + "?key1=val1&key2=val2"
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Synthetic
        assert wsgi_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/" == wsgi_span.data["http"]["url"]
        assert wsgi_span.data["http"]["params"] == "key1=<redacted>&key2=<redacted>"
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_get_request_with_suppression(self) -> None:
        headers = {'X-INSTANA-L':'0'}
        response = self.http.urlopen('GET', testenv["flask_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()

        assert response.headers.get("X-INSTANA-L", None) == "0"
        # The traceparent has to be present
        assert response.headers.get("traceparent", None) is not None
        # The last digit of the traceparent has to be 0
        assert response.headers["traceparent"][-1] == "0"

        # This should not be present
        assert response.headers.get("tracestate", None) is None

        # Assert that there are no spans in the recorded list
        assert spans == []

    def test_get_request_with_suppression_and_w3c(self) -> None:
        """Incoming Level 0 Plus W3C Trace Context Specification Headers"""
        headers = {
                'X-INSTANA-L':'0',
                'traceparent': '00-0af7651916cd43dd8448eb211c80319c-b9c7c989f97918e1-01',
                'tracestate': 'congo=ucfJifl5GOE,rojo=00f067aa0ba902b7'}

        response = self.http.urlopen('GET', testenv["flask_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()

        assert response.headers.get("X-INSTANA-L", None) == "0"
        # if X-INSTANA-L=0 then both X-INSTANA-T and X-INSTANA-S should not be present
        assert not response.headers.get("X-INSTANA-T", None)
        assert not response.headers.get("X-INSTANA-S", None)

        assert response.headers.get("traceparent", None) is not None
        assert response.headers["traceparent"].startswith("00-0af7651916cd43dd8448eb211c80319c")
        assert response.headers["traceparent"][-1] == "0"
        # The tracestate has to be present
        assert response.headers.get("tracestate", None) is not None

        # The 'in=' section can not be in the tracestate
        assert "in=" not in response.headers["tracestate"]

        # Assert that there are no spans in the recorded list
        assert spans == []

    def test_synthetic_request(self) -> None:
        headers = {
            'X-INSTANA-SYNTHETIC': '1'
        }

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/', headers=headers)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert wsgi_span.sy
        assert urllib3_span.sy is None
        assert test_span.sy is None

    def test_render_template(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/render')

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        render_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == render_span.t
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s
        assert render_span.p == wsgi_span.s

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None
        assert render_span.ec is None

        # render
        assert "render" == render_span.n
        assert SpanKind.INTERNAL == render_span.k
        assert "flask_render_template.html" == render_span.data["render"]["name"]
        assert "template" == render_span.data["render"]["type"]
        assert render_span.data["log"]["message"] is None
        assert render_span.data["log"]["parameters"] is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/render" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/render" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_render_template_string(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/render_string')

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        render_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == render_span.t
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s
        assert render_span.p == wsgi_span.s

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None
        assert render_span.ec is None

        # render
        assert "render" == render_span.n
        assert SpanKind.INTERNAL == render_span.k
        assert "(from string)" == render_span.data["render"]["name"]
        assert "template" == render_span.data["render"]["type"]
        assert render_span.data["log"]["message"] is None
        assert render_span.data["log"]["parameters"] is None

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/render_string" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/render_string"
            == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_301(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/301', redirect=False)

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 301 == response.status

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert None == urllib3_span.ec
        assert None == wsgi_span.ec

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/301" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 301 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 301 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/301" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_custom_404(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/custom-404')

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 404 == response.status

        # assert 'X-INSTANA-T' in response.headers
        # assert int(response.headers['X-INSTANA-T']) == 16
        # assert response.headers['X-INSTANA-T'] == wsgi_span.t
        #
        # assert 'X-INSTANA-S' in response.headers
        # assert int(response.headers['X-INSTANA-S']) == 16
        # assert response.headers['X-INSTANA-S'] == wsgi_span.s
        #
        # assert 'X-INSTANA-L' in response.headers
        # assert response.headers['X-INSTANA-L'] == '1'
        #
        # assert 'Server-Timing' in response.headers
        # server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        # assert response.headers['Server-Timing'] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert None == urllib3_span.ec
        assert None == wsgi_span.ec

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/custom-404" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 404 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 404 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/custom-404" == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_404(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/11111111111')

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 404 == response.status

        # assert 'X-INSTANA-T' in response.headers
        # assert int(response.headers['X-INSTANA-T']) == 16
        # assert response.headers['X-INSTANA-T'] == wsgi_span.t
        #
        # assert 'X-INSTANA-S' in response.headers
        # assert int(response.headers['X-INSTANA-S']) == 16
        # assert response.headers['X-INSTANA-S'] == wsgi_span.s
        #
        # assert 'X-INSTANA-L' in response.headers
        # assert response.headers['X-INSTANA-L'] == '1'
        #
        # assert 'Server-Timing' in response.headers
        # server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        # assert response.headers['Server-Timing'] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert None == urllib3_span.ec
        assert None == wsgi_span.ec

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/11111111111" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 404 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 404 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/11111111111" == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_500(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/500')

        spans = self.recorder.queued_spans()

        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert 500 == response.status

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert 1 == urllib3_span.ec
        assert 1 == wsgi_span.ec

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/500" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 500 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 500 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/500" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_render_error(self) -> None:
        if signals_available is True:
            raise unittest.SkipTest("Exceptions without handlers vary with blinker")

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/render_error')

        spans = self.recorder.queued_spans()

        assert len(spans) == 4

        log_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert 500 == response.status

        # assert 'X-INSTANA-T' in response.headers
        # assert int(response.headers['X-INSTANA-T']) == 16
        # assert response.headers['X-INSTANA-T'] == wsgi_span.t
        #
        # assert 'X-INSTANA-S' in response.headers
        # assert int(response.headers['X-INSTANA-S']) == 16
        # assert response.headers['X-INSTANA-S'] == wsgi_span.s
        #
        # assert 'X-INSTANA-L' in response.headers
        # assert response.headers['X-INSTANA-L'] == '1'
        #
        # assert 'Server-Timing' in response.headers
        # server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        # assert response.headers['Server-Timing'] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert 1 == urllib3_span.ec
        assert 1 == wsgi_span.ec

        # error log
        assert "log" == log_span.n
        assert log_span.data["log"]["message"] == "Exception on /render_error [GET]"
        assert (
            log_span.data["log"]["parameters"]
            == "<class 'jinja2.exceptions.TemplateSyntaxError'> unexpected '}'"
        )

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/render_error" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 500 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 500 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/render_error" == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_exception(self) -> None:
        if signals_available is True:
            raise unittest.SkipTest("Exceptions without handlers vary with blinker")

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/exception')

        spans = self.recorder.queued_spans()

        assert len(spans) == 4

        log_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert 500 == response.status

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s
        assert log_span.p == wsgi_span.s

        # Error logging
        assert test_span.ec is None
        assert 1 == urllib3_span.ec
        assert 1 == wsgi_span.ec
        assert 1 == log_span.ec

        # error log
        assert "log" == log_span.n
        assert log_span.data["log"]["message"] == "Exception on /exception [GET]"
        assert log_span.data["log"]["parameters"] == "<class 'Exception'> fake error"

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/exception" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 500 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 500 == urllib3_span.data["http"]["status"]
        assert testenv["flask_server"] + "/exception" == urllib3_span.data["http"]["url"]
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_custom_exception_with_log(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/exception-invalid-usage')

        spans = self.recorder.queued_spans()

        assert len(spans) == 4

        log_span = spans[0]
        wsgi_span = spans[1]
        urllib3_span = spans[2]
        test_span = spans[3]

        assert response
        assert 502 == response.status

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert test_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert test_span.ec is None
        assert 1 == urllib3_span.ec
        assert 1 == wsgi_span.ec
        assert 1 == log_span.ec

        # error log
        assert "log" == log_span.n
        assert log_span.data["log"]["message"] == "InvalidUsage error handler invoked"
        assert (
            log_span.data["log"]["parameters"]
            == "<class 'tests.apps.flask_app.app.InvalidUsage'> "
        )

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/exception-invalid-usage" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 502 == wsgi_span.data["http"]["status"]
        assert "Simulated custom exception" == wsgi_span.data["http"]["error"]
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 502 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/exception-invalid-usage"
            == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should NOT have a path template for this route
        assert wsgi_span.data["http"]["path_tpl"] is None

    def test_path_templates(self) -> None:
        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/users/Ricky/sayhello')

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200

        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

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
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/users/Ricky/sayhello" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/users/Ricky/sayhello"
            == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # We should have a reported path template for this route
        assert "/users/{username}/sayhello" == wsgi_span.data["http"]["path_tpl"]

    def test_request_header_capture(self) -> None:
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        with tracer.start_as_current_span("test"):
            response = self.http.request(
                "GET", testenv["flask_server"] + "/", headers=request_headers
            )

        assert response
        assert response.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        assert wsgi_span.ec is None
        assert wsgi_span.stack is None

        assert "/" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]

        assert "X-Capture-This-Too" in wsgi_span.data["http"]["header"]
        assert "this too" == wsgi_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in wsgi_span.data["http"]["header"]
        assert "that too" == wsgi_span.data["http"]["header"]["X-Capture-That-Too"]

        agent.options.extra_http_headers = original_extra_http_headers


    def test_response_header_capture(self) -> None:
        # Hack together a manual custom headers list
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        with tracer.start_as_current_span("test"):
            response = self.http.request('GET', testenv["flask_server"] + '/response_headers')

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert response
        assert response.status == 200
        assert "X-INSTANA-T" in response.headers
        assert int(response.headers["X-INSTANA-T"], 16)
        assert response.headers["X-INSTANA-T"] == hex_id(wsgi_span.t)

        assert "X-INSTANA-S" in response.headers
        assert int(response.headers["X-INSTANA-S"], 16)
        assert response.headers["X-INSTANA-S"] == hex_id(wsgi_span.s)

        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"

        assert "Server-Timing" in response.headers
        server_timing_value = f"intid;desc={hex_id(wsgi_span.t)}"
        assert response.headers["Server-Timing"] == server_timing_value

        assert get_current_span().is_recording() is False

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Synthetic
        assert wsgi_span.sy is None
        assert urllib3_span.sy is None
        assert test_span.sy is None

        # Error logging
        assert test_span.ec is None
        assert urllib3_span.ec is None
        assert wsgi_span.ec is None

        # urllib3
        assert "test" == test_span.data["sdk"]["name"]
        assert "urllib3" == urllib3_span.n
        assert 200 == urllib3_span.data["http"]["status"]
        assert (
            testenv["flask_server"] + "/response_headers"
            == urllib3_span.data["http"]["url"]
        )
        assert "GET" == urllib3_span.data["http"]["method"]
        assert urllib3_span.stack is not None
        assert type(urllib3_span.stack) is list
        assert len(urllib3_span.stack) > 1

        # wsgi
        assert "wsgi" == wsgi_span.n
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/response_headers" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert 200 == wsgi_span.data["http"]["status"]
        assert wsgi_span.data["http"]["error"] is None
        assert wsgi_span.stack is None

        assert "X-Capture-This" in wsgi_span.data["http"]["header"]
        assert "Ok" == wsgi_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in wsgi_span.data["http"]["header"]

        assert "Ok too" == wsgi_span.data["http"]["header"]["X-Capture-That"]

        agent.options.extra_http_headers = original_extra_http_headers

    def test_request_started_exception(self) -> None:
        with tracer.start_as_current_span("test"):
            with patch(
                "instana.singletons.tracer.extract",
                side_effect=Exception("mocked error"),
            ):
                self.http.request("GET", testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

    @unittest.skipIf(
        not signals_available,
        "log_exception_with_instana needs to be covered only with blinker",
    )
    def test_got_request_exception(self) -> None:
        response = self.http.request(
            "GET", testenv["flask_server"] + "/got_request_exception"
        )

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        wsgi_span = spans[0]

        assert response
        assert 500 == response.status

        assert get_current_span().is_recording() is False

        # Error logging
        assert wsgi_span.ec == 1

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert (
            "127.0.0.1:" + str(testenv["flask_port"]) == wsgi_span.data["http"]["host"]
        )
        assert "/got_request_exception" == wsgi_span.data["http"]["url"]
        assert "GET" == wsgi_span.data["http"]["method"]
        assert wsgi_span.data["http"]["status"] == 500
        assert wsgi_span.data["http"]["error"] == "RuntimeError()"
        assert wsgi_span.stack is None
