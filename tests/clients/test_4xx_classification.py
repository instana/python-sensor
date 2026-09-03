# (c) Copyright IBM Corp. 2026

"""
Integration tests for HTTP exit span 4xx error classification.

Tests cover the three configuration modes against real server spans for:
  - urllib3
  - httpx
  - aiohttp client
  - tornado client
  - twisted client

For every HTTP client the test matrix is:

  1. default (opt-in off)  → exit ec=0, entry ec=0 for 4xx
  2. classify_all=True     → exit ec=1, entry ec=0 for 4xx
  3. classify_codes=[401]  → exit ec=1 for 401, ec=0 for 404; entry never changed

Server apps used:
  - Flask  (urllib3, httpx tests)
  - aiohttp server (aiohttp client tests)
  - tornado server (tornado client tests)
  - twisted server (twisted client tests)

All tests clean up options.http_exit_classify_* in teardown.
"""

import asyncio
import threading
import time
from collections.abc import Generator
from typing import Optional  # noqa: UP035 — keep typing import separate for clarity

import aiohttp
import httpx
import pytest
import tornado
import tornado.ioloop
import urllib3
from tornado.httpclient import AsyncHTTPClient
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

import tests.apps.aiohttp_app  # noqa: F401 — starts aiohttp server
import tests.apps.flask_app  # noqa: F401 — starts Flask server
import tests.apps.tornado_server  # noqa: F401 — starts tornado server
import tests.apps.twisted_server  # noqa: F401 — starts twisted server
from instana.singletons import agent, get_tracer
from tests.helpers import get_first_span_by_name, testenv

# ---------------------------------------------------------------------------
# shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_4xx_opts() -> Generator[None, None, None]:
    """Ensure 4xx classification options are clean before and after every test."""
    agent.options.http_exit_classify_all_4xx_as_errors = False
    agent.options.http_exit_classify_as_errors = []
    yield
    agent.options.http_exit_classify_all_4xx_as_errors = False
    agent.options.http_exit_classify_as_errors = []


# ---------------------------------------------------------------------------
# urllib3
# ---------------------------------------------------------------------------


class TestUrllib34xxClassification:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        self.http = urllib3.PoolManager()
        yield

    def test_default_400_not_error(self) -> None:
        """With default config, 400 exit span must NOT be errored."""
        with self.tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/400")

        assert r.status == 400
        spans = self.recorder.queued_spans()
        # 3 spans: sdk(test) → urllib3 → wsgi
        exit_span = get_first_span_by_name(spans, "urllib3")
        assert exit_span is not None
        assert not exit_span.ec, "default: 400 must not be errored on exit span"

        entry_span = get_first_span_by_name(spans, "wsgi")
        assert entry_span is not None
        assert not entry_span.ec, "entry span must never be errored by 4xx classification"

    def test_classify_all_400_is_error(self) -> None:
        """With classify_all=True, 400 exit span MUST be errored."""
        agent.options.http_exit_classify_all_4xx_as_errors = True

        with self.tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/400")

        assert r.status == 400
        spans = self.recorder.queued_spans()
        exit_span = get_first_span_by_name(spans, "urllib3")
        assert exit_span is not None
        assert exit_span.ec == 1, "classify_all: 400 must be errored on exit span"

        entry_span = get_first_span_by_name(spans, "wsgi")
        assert entry_span is not None
        assert not entry_span.ec, "entry span must never be errored by 4xx classification"

    def test_classify_codes_400_is_error_404_is_not(self) -> None:
        """With classify_codes=[400], 400→ec=1 but 405→ec=0."""
        agent.options.http_exit_classify_as_errors = [400]

        with self.tracer.start_as_current_span("test"):
            r400 = self.http.request("GET", testenv["flask_server"] + "/400")
        spans_400 = self.recorder.queued_spans()
        self.recorder.clear_spans()

        with self.tracer.start_as_current_span("test"):
            r405 = self.http.request("GET", testenv["flask_server"] + "/405")
        spans_405 = self.recorder.queued_spans()

        assert r400.status == 400
        exit_400 = get_first_span_by_name(spans_400, "urllib3")
        assert exit_400 is not None
        assert exit_400.ec == 1, "400 in classify list must be errored"

        assert r405.status == 405
        exit_405 = get_first_span_by_name(spans_405, "urllib3")
        assert exit_405 is not None
        assert not exit_405.ec, "405 NOT in classify list must not be errored"


# ---------------------------------------------------------------------------
# httpx
# ---------------------------------------------------------------------------


class TestHttpx4xxClassification:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        yield

    def test_default_400_not_error(self) -> None:
        with self.tracer.start_as_current_span("test"):
            r = httpx.get(testenv["flask_server"] + "/400")

        assert r.status_code == 400
        spans = self.recorder.queued_spans()
        # httpx span name is registered as "http", entry (Flask/wsgi) is "wsgi"
        exit_span = get_first_span_by_name(spans, "http")
        assert exit_span is not None
        assert not exit_span.ec, "default: 400 must not be errored on exit span"

        entry_span = get_first_span_by_name(spans, "wsgi")
        assert entry_span is not None
        assert not entry_span.ec

    def test_classify_all_400_is_error(self) -> None:
        agent.options.http_exit_classify_all_4xx_as_errors = True

        with self.tracer.start_as_current_span("test"):
            r = httpx.get(testenv["flask_server"] + "/400")

        assert r.status_code == 400
        spans = self.recorder.queued_spans()
        exit_span = get_first_span_by_name(spans, "http")
        assert exit_span is not None
        assert exit_span.ec == 1, "classify_all: 400 must be errored on exit span"

        entry_span = get_first_span_by_name(spans, "wsgi")
        assert entry_span is not None
        assert not entry_span.ec

    def test_classify_codes_selective(self) -> None:
        agent.options.http_exit_classify_as_errors = [400]

        with self.tracer.start_as_current_span("test"):
            httpx.get(testenv["flask_server"] + "/400")
        spans_400 = self.recorder.queued_spans()
        self.recorder.clear_spans()

        with self.tracer.start_as_current_span("test"):
            httpx.get(testenv["flask_server"] + "/405")
        spans_405 = self.recorder.queued_spans()

        exit_400 = get_first_span_by_name(spans_400, "http")
        assert exit_400 is not None and exit_400.ec == 1

        exit_405 = get_first_span_by_name(spans_405, "http")
        assert exit_405 is not None and not exit_405.ec


# ---------------------------------------------------------------------------
# aiohttp client
# ---------------------------------------------------------------------------


class TestAiohttpClient4xxClassification:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        yield
        self.loop.close()

    def _run(self, coro) -> object:
        return self.loop.run_until_complete(coro)

    async def _fetch(self, url: str) -> int:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    return resp.status
            except aiohttp.ClientResponseError as e:
                return e.status

    def test_default_401_not_error(self) -> None:
        with self.tracer.start_as_current_span("test"):
            status = self._run(self._fetch(testenv["aiohttp_server"] + "/401"))

        assert status == 401
        spans = self.recorder.queued_spans()
        exit_span = get_first_span_by_name(spans, "aiohttp-client")
        assert exit_span is not None
        assert not exit_span.ec, "default: 401 must not be errored"

    def test_classify_all_401_is_error(self) -> None:
        agent.options.http_exit_classify_all_4xx_as_errors = True

        with self.tracer.start_as_current_span("test"):
            status = self._run(self._fetch(testenv["aiohttp_server"] + "/401"))

        assert status == 401
        spans = self.recorder.queued_spans()
        exit_span = get_first_span_by_name(spans, "aiohttp-client")
        assert exit_span is not None
        assert exit_span.ec == 1, "classify_all: 401 must be errored"

    def test_classify_codes_401_is_error(self) -> None:
        agent.options.http_exit_classify_as_errors = [401]

        with self.tracer.start_as_current_span("test"):
            status = self._run(self._fetch(testenv["aiohttp_server"] + "/401"))

        assert status == 401
        spans = self.recorder.queued_spans()
        exit_span = get_first_span_by_name(spans, "aiohttp-client")
        assert exit_span is not None
        assert exit_span.ec == 1


# ---------------------------------------------------------------------------
# tornado client
# ---------------------------------------------------------------------------


class TestTornadoClient4xxClassification:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        # New event loop for every test — same pattern as test_tornado_client.py
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.http_client = AsyncHTTPClient()
        yield
        self.http_client.close()

    def test_default_405_client_exception_is_error(self) -> None:
        """405 raises HTTPClientError → tornado already marks ec=1 via record_exception."""
        async def test():
            with self.tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(
                        testenv["tornado_server"] + "/405"
                    )
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        server_span = get_first_span_by_name(spans, "tornado-server")
        assert client_span is not None
        assert client_span.ec == 1, "405 HTTPClientError must always errored via record_exception"
        assert server_span is not None
        assert not server_span.ec, "entry span must not be errored"

    def test_classify_all_405_is_error(self) -> None:
        """With classify_all=True, HTTPClientError path: 405→ec=1 (same as default,
        since record_exception already sets ec).  More importantly, entry span stays ec=0."""
        agent.options.http_exit_classify_all_4xx_as_errors = True

        async def test():
            with self.tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(
                        testenv["tornado_server"] + "/405"
                    )
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        server_span = get_first_span_by_name(spans, "tornado-server")
        assert client_span is not None
        assert client_span.ec == 1
        assert server_span is not None
        assert not server_span.ec, "entry span must never be errored by 4xx classification"

    def test_classify_codes_405_in_list_is_error(self) -> None:
        """With classify_codes=[405], HTTPClientError path still marks ec=1 (record_exception)."""
        agent.options.http_exit_classify_as_errors = [405]

        async def test():
            with self.tracer.start_as_current_span("test"):
                try:
                    return await self.http_client.fetch(
                        testenv["tornado_server"] + "/405"
                    )
                except tornado.httpclient.HTTPClientError as e:
                    return e.response

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        assert client_span is not None
        assert client_span.ec == 1

    # ------------------------------------------------------------------
    # raise_error=False tests — exercise should_mark_http_exit_as_error
    # happy path in finish_tracing (no HTTPClientError raised)
    # ------------------------------------------------------------------

    def test_raise_error_false_default_405_not_error(self) -> None:
        """raise_error=False: 405 response arrives on the happy path of finish_tracing.
        With no opt-in active the exit span must NOT be errored."""

        async def test():
            with self.tracer.start_as_current_span("test"):
                return await self.http_client.fetch(
                    testenv["tornado_server"] + "/405", raise_error=False
                )

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        server_span = get_first_span_by_name(spans, "tornado-server")
        assert client_span is not None
        assert not client_span.ec, "default: 405 must not be errored on exit span"
        assert server_span is not None
        assert not server_span.ec, "entry span must not be errored"

    def test_raise_error_false_classify_all_405_is_error(self) -> None:
        """raise_error=False + classify_all=True: should_mark_http_exit_as_error() runs
        on the happy path and must set ec=1 on the exit span; entry span stays ec=0."""
        agent.options.http_exit_classify_all_4xx_as_errors = True

        async def test():
            with self.tracer.start_as_current_span("test"):
                return await self.http_client.fetch(
                    testenv["tornado_server"] + "/405", raise_error=False
                )

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        server_span = get_first_span_by_name(spans, "tornado-server")
        assert client_span is not None
        assert client_span.ec == 1, "classify_all: 405 must be errored on exit span"
        assert client_span.data["http"]["error"] == "405 Method Not Allowed", "http.error must be set"
        assert server_span is not None
        assert not server_span.ec, "entry span must never be errored by 4xx classification"

    def test_raise_error_false_classify_codes_405_in_list_is_error(self) -> None:
        """raise_error=False + classify_codes=[405]: should_mark_http_exit_as_error()
        must return True for 405 and set ec=1; a code not in the list (e.g. 301) stays ec=0."""
        agent.options.http_exit_classify_as_errors = [405]

        async def test():
            with self.tracer.start_as_current_span("test"):
                return await self.http_client.fetch(
                    testenv["tornado_server"] + "/405", raise_error=False
                )

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        assert client_span is not None
        assert client_span.ec == 1, "classify_codes=[405]: 405 must be errored on exit span"
        assert client_span.data["http"]["error"] == "405 Method Not Allowed", "http.error must be set"

    def test_raise_error_false_classify_codes_405_not_in_list_not_error(self) -> None:
        """raise_error=False + classify_codes=[401]: 405 is NOT in the list → ec must stay 0."""
        agent.options.http_exit_classify_as_errors = [401]

        async def test():
            with self.tracer.start_as_current_span("test"):
                return await self.http_client.fetch(
                    testenv["tornado_server"] + "/405", raise_error=False
                )

        tornado.ioloop.IOLoop.current().run_sync(test)
        time.sleep(0.3)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "tornado-client")
        assert client_span is not None
        assert not client_span.ec, "classify_codes=[401]: 405 must NOT be errored"


# ---------------------------------------------------------------------------
# twisted client
# ---------------------------------------------------------------------------


class TestTwistedClient4xxClassification:
    """4xx error classification tests for the Twisted HTTP client.

    Uses ``tests.apps.twisted_server`` (started once per session via module-level
    import) as the upstream target.  Each test fires a Twisted ``Agent.request``
    from a background thread via ``reactor.callFromThread`` — the same pattern
    used by ``TestTwistedClient``.

    Span tree per request:
        sdk("test")  →  twisted-client  →  twisted-server
    """

    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        yield

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _make_request(self, path: str) -> Optional[object]:
        """Fire GET <twisted_server><path> inside a test span; return the response."""
        result_holder: dict = {}
        event = threading.Event()

        def run() -> None:
            with self.tracer.start_as_current_span("test"):
                agent_obj = Agent(reactor)
                url = (testenv["twisted_server"] + path).encode("utf-8")
                d = agent_obj.request(b"GET", url, Headers({}), None)

                def on_response(response: object) -> object:
                    result_holder["response"] = response
                    return response

                def on_error(failure: object) -> object:
                    result_holder["failure"] = failure
                    return failure

                d.addCallbacks(on_response, on_error)

                def done(_: object) -> None:
                    event.set()

                d.addBoth(done)

        reactor.callFromThread(run)
        event.wait(timeout=5)
        return result_holder.get("response")

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_default_401_not_error(self) -> None:
        """With default config, 401 exit span must NOT be errored."""
        response = self._make_request("/401")
        assert response is not None
        assert response.code == 401

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "twisted-client")
        assert client_span is not None
        assert not client_span.ec, "default: 401 must not be errored on exit span"
        assert client_span.data["http"]["status"] == 401

        server_span = get_first_span_by_name(spans, "twisted-server")
        assert server_span is not None
        assert not server_span.ec, "entry span must never be errored by 4xx classification"

    def test_classify_all_401_is_error(self) -> None:
        """With classify_all=True, 401 exit span MUST be errored; entry span must not."""
        agent.options.http_exit_classify_all_4xx_as_errors = True

        response = self._make_request("/401")
        assert response is not None
        assert response.code == 401

        time.sleep(0.5)
        spans = self.recorder.queued_spans()

        client_span = get_first_span_by_name(spans, "twisted-client")
        assert client_span is not None
        assert client_span.ec == 1, "classify_all: 401 must be errored on exit span"
        assert client_span.data["http"]["error"] == "401 Unauthorized"

        server_span = get_first_span_by_name(spans, "twisted-server")
        assert server_span is not None
        assert not server_span.ec, "entry span must never be errored by 4xx classification"

    def test_classify_codes_401_is_error_403_is_not(self) -> None:
        """With classify_codes=[401], 401→ec=1 but 403→ec=0; entry spans unaffected."""
        agent.options.http_exit_classify_as_errors = [401]

        response_401 = self._make_request("/401")
        assert response_401 is not None
        assert response_401.code == 401

        time.sleep(0.5)
        spans_401 = self.recorder.queued_spans()
        self.recorder.clear_spans()

        response_403 = self._make_request("/403")
        assert response_403 is not None
        assert response_403.code == 403

        time.sleep(0.5)
        spans_403 = self.recorder.queued_spans()

        client_401 = get_first_span_by_name(spans_401, "twisted-client")
        assert client_401 is not None
        assert client_401.ec == 1, "401 in classify list must be errored"
        assert client_401.data["http"]["error"] == "401 Unauthorized"

        server_401 = get_first_span_by_name(spans_401, "twisted-server")
        assert server_401 is not None
        assert not server_401.ec, "entry span must never be errored by 4xx classification"

        client_403 = get_first_span_by_name(spans_403, "twisted-client")
        assert client_403 is not None
        assert not client_403.ec, "403 NOT in classify list must not be errored"

        server_403 = get_first_span_by_name(spans_403, "twisted-server")
        assert server_403 is not None
        assert not server_403.ec, "entry span must never be errored by 4xx classification"

    def test_classify_all_overridden_by_classify_codes(self) -> None:
        """classify_codes non-empty overrides classify_all per spec precedence rule.

        classify_all=True + classify_codes=[403] → only 403 gets ec=1; 401 stays ec=0.
        """
        agent.options.http_exit_classify_all_4xx_as_errors = True
        agent.options.http_exit_classify_as_errors = [403]

        response_401 = self._make_request("/401")
        assert response_401 is not None
        assert response_401.code == 401

        time.sleep(0.5)
        spans_401 = self.recorder.queued_spans()
        self.recorder.clear_spans()

        response_403 = self._make_request("/403")
        assert response_403 is not None
        assert response_403.code == 403

        time.sleep(0.5)
        spans_403 = self.recorder.queued_spans()

        client_401 = get_first_span_by_name(spans_401, "twisted-client")
        assert client_401 is not None
        assert not client_401.ec, "classify_codes overrides classify_all: 401 must not be errored"

        client_403 = get_first_span_by_name(spans_403, "twisted-client")
        assert client_403 is not None
        assert client_403.ec == 1, "403 in classify_codes must be errored even with classify_all"
