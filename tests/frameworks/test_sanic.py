# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

import pytest
from typing import Generator
from sanic_testing.testing import SanicTestClient

from instana.singletons import tracer, agent
from instana.util.ids import hex_id
from tests.helpers import get_first_span_by_filter, get_first_span_by_name, is_test_span
from tests.test_utils import _TraceContextMixin
from tests.apps.sanic_app.server import app


class TestSanic(_TraceContextMixin):
    @classmethod
    def setup_class(cls) -> None:
        cls.client = SanicTestClient(app, port=1337, host="127.0.0.1")
        cls.endpoint = f"{cls.client.host}:{cls.client.port}"

        # Hack together a manual custom headers list; We'll use this in tests
        agent.options.extra_http_headers = [
            "X-Capture-This",
            "X-Capture-That",
            "X-Capture-This-Too",
            "X-Capture-That-Too",
        ]

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()

    def test_vanilla_get(self) -> None:
        request, response = self.client.get("/")

        assert response.status_code == 200
        assert "X-INSTANA-T" in response.headers
        assert "X-INSTANA-S" in response.headers
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].n == "asgi"

    def test_basic_get(self) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_404(self) -> None:
        path = "/foo/not_an_int"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 404

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 404
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert not asgi_span.data["http"]["path_tpl"]
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 404
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_sanic_exception(self) -> None:
        path = "/wrong"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 400

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 400
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 400
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500_instana_exception(self) -> None:
        path = "/instana_exception"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 500
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_500(self) -> None:
        path = "/test_request_args"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 500

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 500
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert asgi_span.ec == 1
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 500
        assert asgi_span.data["http"]["error"] == "Something went wrong."
        assert not asgi_span.data["http"]["params"]

    def test_path_templates(self) -> None:
        path = "/foo/1"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == "/foo/<foo_id:int>"
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

    def test_secret_scrubbing(self) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path+"?secret=shhh")

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert asgi_span.data["http"]["params"] == "secret=<redacted>"

    def test_synthetic_request(self) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            headers = {
                "X-INSTANA-SYNTHETIC": "1",
            }
            request, response = self.client.get(path, headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        assert "X-INSTANA-T" in response.headers
        assert response.headers["X-INSTANA-T"] == hex_id(asgi_span.t)
        assert "X-INSTANA-S" in response.headers
        assert response.headers["X-INSTANA-S"] == hex_id(asgi_span.s)
        assert "X-INSTANA-L" in response.headers
        assert response.headers["X-INSTANA-L"] == "1"
        assert "Server-Timing" in response.headers
        assert response.headers["Server-Timing"] == f"intid;desc={hex_id(asgi_span.t)}"

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert asgi_span.sy
        assert not httpx_span.sy
        assert not test_span.sy

    def test_request_header_capture(self) -> None:
        path = "/"
        with tracer.start_as_current_span("test"):
            headers = {
                "X-Capture-This": "this",
                "X-Capture-That": "that",
            }
            request, response = self.client.get(path, headers=headers)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This" in asgi_span.data["http"]["header"]
        assert "this" == asgi_span.data["http"]["header"]["X-Capture-This"]
        assert "X-Capture-That" in asgi_span.data["http"]["header"]
        assert "that" == asgi_span.data["http"]["header"]["X-Capture-That"]

    def test_response_header_capture(self) -> None:
        path = "/response_headers"
        with tracer.start_as_current_span("test"):
            request, response = self.client.get(path)

        assert response.status_code == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_filter(spans, is_test_span)
        assert test_span

        httpx_span = get_first_span_by_name(spans, "http")
        assert httpx_span

        asgi_span = get_first_span_by_name(spans, "asgi")
        assert asgi_span

        self.assertTraceContextPropagated(test_span, httpx_span)
        self.assertTraceContextPropagated(httpx_span, asgi_span)

        # httpx
        assert httpx_span.data["http"]["status"] == 200
        assert httpx_span.data["http"]["host"] == self.client.host
        assert httpx_span.data["http"]["path"] == path
        assert httpx_span.data["http"]["url"] == f"http://{self.endpoint}{path}"
        assert httpx_span.data["http"]["method"] == "GET"
        assert httpx_span.stack
        assert isinstance(httpx_span.stack, list)
        assert len(httpx_span.stack) > 1

        # sanic
        assert not asgi_span.ec
        assert asgi_span.data["http"]["host"] == self.endpoint
        assert asgi_span.data["http"]["path"] == path
        assert asgi_span.data["http"]["path_tpl"] == path
        assert asgi_span.data["http"]["method"] == "GET"
        assert asgi_span.data["http"]["status"] == 200
        assert not asgi_span.data["http"]["error"]
        assert not asgi_span.data["http"]["params"]

        assert "X-Capture-This-Too" in asgi_span.data["http"]["header"]
        assert "this too" == asgi_span.data["http"]["header"]["X-Capture-This-Too"]
        assert "X-Capture-That-Too" in asgi_span.data["http"]["header"]
        assert "that too" == asgi_span.data["http"]["header"]["X-Capture-That-Too"]
