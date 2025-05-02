# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
import sys
from multiprocessing.pool import ThreadPool
from time import sleep
from typing import TYPE_CHECKING, Generator

import pytest
import requests
import urllib3
from instana.instrumentation.urllib3 import (
    _collect_kvs as collect_kvs,
    extract_custom_headers,
    collect_response,
)
from instana.singletons import agent, tracer

import tests.apps.flask_app  # noqa: F401
from tests.helpers import testenv

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan
    from pytest import LogCaptureFixture


class TestUrllib3:
    @pytest.fixture(autouse=True)
    def _setup(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.http = urllib3.PoolManager()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield
        # teardown
        # Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False

    def test_vanilla_requests(self) -> None:
        r = self.http.request("GET", testenv["flask_server"] + "/")
        assert r.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    def test_parallel_requests(self) -> None:
        http_pool_5 = urllib3.PoolManager(num_pools=5)

        def task(num):
            r = http_pool_5.request(
                "GET", testenv["flask_server"] + "/", fields={"num": num}
            )
            return r

        with ThreadPool(processes=5) as executor:
            # iterate over results as they become available
            for result in executor.map(task, (1, 2, 3, 4, 5)):
                assert result.status == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 5
        nums = map(lambda s: s.data["http"]["params"].split("=")[1], spans)
        assert set(nums) == set(("1", "2", "3", "4", "5"))

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="Avoiding ConnectionError when calling multi processes of Flask app.",
    )
    def test_customers_setup_zd_26466(self) -> None:
        def make_request(u=None) -> int:
            sleep(10)
            x = requests.get(testenv["flask_server"] + "/")
            sleep(10)
            return x.status_code

        status = make_request()
        assert status == 200
        # print(f'request made outside threadpool, instana should instrument - status: {status}')

        threadpool_size = 15
        pool = ThreadPool(processes=threadpool_size)
        _ = pool.map(make_request, [u for u in range(threadpool_size)])
        # print(f'requests made within threadpool, instana does not instrument - statuses: {res}')

        spans = self.recorder.queued_spans()
        assert len(spans) == 16

    def test_get_request(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 200

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_get_request_https(self):
        request_url = "https://jsonplaceholder.typicode.com:443/todos/1"
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", request_url)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        urllib3_span = spans[0]
        test_span = spans[1]

        assert r
        assert r.status == 200

        # Same traceId
        assert test_span.t == urllib3_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == request_url
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_get_request_as_root_exit_span(self):
        agent.options.allow_exit_as_root = True
        r = self.http.request("GET", testenv["flask_server"] + "/")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        wsgi_span = spans[0]
        urllib3_span = spans[1]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert not urllib3_span.p
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_get_request_with_query(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/?one=1&two=2")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["params"] in ["one=1&two=2", "two=2&one=1"]
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_get_request_with_alt_query(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request(
                "GET", testenv["flask_server"] + "/", fields={"one": "1", "two": 2}
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["params"] in ["one=1&two=2", "two=2&one=1"]
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_put_request(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("PUT", testenv["flask_server"] + "/notfound")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 404
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/notfound"
        assert wsgi_span.data["http"]["method"] == "PUT"
        assert wsgi_span.data["http"]["status"] == 404
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 404
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/notfound"
        assert urllib3_span.data["http"]["method"] == "PUT"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_301_redirect(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/301")

        spans = self.recorder.queued_spans()
        assert len(spans) == 5

        wsgi_span2 = spans[0]
        urllib3_span2 = spans[1]
        wsgi_span1 = spans[2]
        urllib3_span1 = spans[3]
        test_span = spans[4]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        traceId = test_span.t
        assert urllib3_span1.t == traceId
        assert wsgi_span1.t == traceId
        assert urllib3_span2.t == traceId
        assert wsgi_span2.t == traceId

        # Parent relationships
        assert urllib3_span1.p == test_span.s
        assert wsgi_span1.p == urllib3_span1.s
        assert urllib3_span2.p == test_span.s
        assert wsgi_span2.p == urllib3_span2.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span1.ec
        assert not wsgi_span1.ec
        assert not urllib3_span2.ec
        assert not wsgi_span2.ec

        # wsgi
        assert wsgi_span1.n == "wsgi"
        assert wsgi_span1.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span1.data["http"]["url"] == "/"
        assert wsgi_span1.data["http"]["method"] == "GET"
        assert wsgi_span1.data["http"]["status"] == 200
        assert not wsgi_span1.data["http"]["error"]
        assert not wsgi_span1.stack

        assert wsgi_span2.n == "wsgi"
        assert wsgi_span2.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span2.data["http"]["url"] == "/301"
        assert wsgi_span2.data["http"]["method"] == "GET"
        assert wsgi_span2.data["http"]["status"] == 301
        assert not wsgi_span2.data["http"]["error"]
        assert not wsgi_span2.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span1.n == "urllib3"
        assert urllib3_span1.data["http"]["status"] == 200
        assert urllib3_span1.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span1.data["http"]["method"] == "GET"
        assert urllib3_span1.stack
        assert isinstance(urllib3_span1.stack, list)
        assert len(urllib3_span1.stack) > 1

        assert urllib3_span2.n == "urllib3"
        assert urllib3_span2.data["http"]["status"] == 301
        assert urllib3_span2.data["http"]["url"] == testenv["flask_server"] + "/301"
        assert urllib3_span2.data["http"]["method"] == "GET"
        assert urllib3_span2.stack
        assert isinstance(urllib3_span2.stack, list)
        assert len(urllib3_span2.stack) > 1

    def test_302_redirect(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/302")

        spans = self.recorder.queued_spans()
        assert len(spans) == 5

        wsgi_span2 = spans[0]
        urllib3_span2 = spans[1]
        wsgi_span1 = spans[2]
        urllib3_span1 = spans[3]
        test_span = spans[4]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        traceId = test_span.t
        assert urllib3_span1.t == traceId
        assert wsgi_span1.t == traceId
        assert urllib3_span2.t == traceId
        assert wsgi_span2.t == traceId

        # Parent relationships
        assert urllib3_span1.p == test_span.s
        assert wsgi_span1.p == urllib3_span1.s
        assert urllib3_span2.p == test_span.s
        assert wsgi_span2.p == urllib3_span2.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span1.ec
        assert not wsgi_span1.ec
        assert not urllib3_span2.ec
        assert not wsgi_span2.ec

        # wsgi
        assert wsgi_span1.n == "wsgi"
        assert wsgi_span1.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span1.data["http"]["url"] == "/"
        assert wsgi_span1.data["http"]["method"] == "GET"
        assert wsgi_span1.data["http"]["status"] == 200
        assert not wsgi_span1.data["http"]["error"]
        assert not wsgi_span1.stack

        assert wsgi_span2.n == "wsgi"
        assert wsgi_span2.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span2.data["http"]["url"] == "/302"
        assert wsgi_span2.data["http"]["method"] == "GET"
        assert wsgi_span2.data["http"]["status"] == 302
        assert not wsgi_span2.data["http"]["error"]
        assert not wsgi_span2.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span1.n == "urllib3"
        assert urllib3_span1.data["http"]["status"] == 200
        assert urllib3_span1.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span1.data["http"]["method"] == "GET"
        assert urllib3_span1.stack
        assert isinstance(urllib3_span1.stack, list)
        assert len(urllib3_span1.stack) > 1

        assert urllib3_span2.n == "urllib3"
        assert urllib3_span2.data["http"]["status"] == 302
        assert urllib3_span2.data["http"]["url"] == testenv["flask_server"] + "/302"
        assert urllib3_span2.data["http"]["method"] == "GET"
        assert urllib3_span2.stack
        assert isinstance(urllib3_span2.stack, list)
        assert len(urllib3_span2.stack) > 1

    def test_5xx_request(self):
        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/504")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 504
        # assert not tracer.active_span

        # Same traceId
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert urllib3_span.ec == 1
        assert wsgi_span.ec == 1

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/504"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 504
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 504
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/504"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_exception_logging(self):
        with tracer.start_as_current_span("test"):
            try:
                r = self.http.request("GET", testenv["flask_server"] + "/exception")
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        # Behind the "wsgi_server", currently there is Flask
        # Flask <  2.3.0 optionally can depend on "blinker"
        # Flask >= 2.3.0 unconditionally depends on "blinker"
        # Depending on whether we instrument with "flask/vanilla.py" or "flask/with_blinker.py"
        # The exception logging differs. See the log_exception_with_instana function in flask/with_blinker.py
        # which is called in the blinker scenario.
        # Without blinker, Flask does some extra logging, which results an extra log span recorded
        # but was disregarded by this TC anyway, so for the rest of the TC
        # we will just discard the optional log span if present
        # Without blinker, our instrumentation logs roughly the same exception data onto the
        # already existing wsgi span. Which we validate in this TC if present.
        assert len(spans) in (3, 4)

        with_blinker = len(spans) == 3
        if not with_blinker:
            spans = spans[1:]

        wsgi_span, urllib3_span, test_span = spans

        assert r
        assert r.status == 500
        # assert not tracer.active_span

        # Same traceId
        traceId = test_span.t
        assert urllib3_span.t == traceId
        assert wsgi_span.t == traceId

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert urllib3_span.ec == 1
        assert wsgi_span.ec == 1

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/exception"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 500
        if with_blinker:
            assert wsgi_span.data["http"]["error"] == "fake error"
        else:
            assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 500
        assert (
            urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/exception"
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_client_error(self):
        r = None
        with tracer.start_as_current_span("test"):
            try:
                r = self.http.request(
                    "GET",
                    "http://doesnotexist.asdf:5000/504",
                    retries=False,
                    timeout=urllib3.Timeout(connect=0.5, read=0.5),
                )
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        urllib3_span = spans[0]
        test_span = spans[1]

        assert not r

        # Parent relationships
        assert urllib3_span.p == test_span.s

        # Same traceId
        traceId = test_span.t
        assert urllib3_span.t == traceId

        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert not urllib3_span.data["http"]["status"]
        assert urllib3_span.data["http"]["url"] == "http://doesnotexist.asdf:5000/504"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

        # Error logging
        assert not test_span.ec
        assert urllib3_span.ec == 2

    def test_requests_pkg_get(self):
        self.recorder.clear_spans()

        with tracer.start_as_current_span("test"):
            r = requests.get(testenv["flask_server"] + "/", timeout=2)

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status_code == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_requests_pkg_get_with_custom_headers(self):
        my_custom_headers = dict()
        my_custom_headers["X-PGL-1"] = "1"

        with tracer.start_as_current_span("test"):
            r = requests.get(
                testenv["flask_server"] + "/", timeout=2, headers=my_custom_headers
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status_code == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_requests_pkg_put(self):
        with tracer.start_as_current_span("test"):
            r = requests.put(testenv["flask_server"] + "/notfound")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r.status_code == 404
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/notfound"
        assert wsgi_span.data["http"]["method"] == "PUT"
        assert wsgi_span.data["http"]["status"] == 404
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 404
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/notfound"
        assert urllib3_span.data["http"]["method"] == "PUT"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

    def test_response_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        with tracer.start_as_current_span("test"):
            r = self.http.request("GET", testenv["flask_server"] + "/response_headers")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/response_headers"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert (
            urllib3_span.data["http"]["url"]
            == testenv["flask_server"] + "/response_headers"
        )
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

        assert "X-Capture-This" in urllib3_span.data["http"]["header"]
        assert urllib3_span.data["http"]["header"]["X-Capture-This"] == "Ok"
        assert "X-Capture-That" in urllib3_span.data["http"]["header"]
        assert urllib3_span.data["http"]["header"]["X-Capture-That"] == "Ok too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_request_header_capture(self):
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }
        with tracer.start_as_current_span("test"):
            r = self.http.request(
                "GET", testenv["flask_server"] + "/", headers=request_headers
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        wsgi_span = spans[0]
        urllib3_span = spans[1]
        test_span = spans[2]

        assert r
        assert r.status == 200
        # assert not tracer.active_span

        # Same traceId
        assert test_span.t == urllib3_span.t
        assert urllib3_span.t == wsgi_span.t

        # Parent relationships
        assert urllib3_span.p == test_span.s
        assert wsgi_span.p == urllib3_span.s

        # Error logging
        assert not test_span.ec
        assert not urllib3_span.ec
        assert not wsgi_span.ec

        # wsgi
        assert wsgi_span.n == "wsgi"
        assert wsgi_span.data["http"]["host"] == "127.0.0.1:" + str(
            testenv["flask_port"]
        )
        assert wsgi_span.data["http"]["url"] == "/"
        assert wsgi_span.data["http"]["method"] == "GET"
        assert wsgi_span.data["http"]["status"] == 200
        assert not wsgi_span.data["http"]["error"]
        assert not wsgi_span.stack

        # urllib3
        assert test_span.data["sdk"]["name"] == "test"
        assert urllib3_span.n == "urllib3"
        assert urllib3_span.data["http"]["status"] == 200
        assert urllib3_span.data["http"]["url"] == testenv["flask_server"] + "/"
        assert urllib3_span.data["http"]["method"] == "GET"
        assert urllib3_span.stack
        assert isinstance(urllib3_span.stack, list)
        assert len(urllib3_span.stack) > 1

        assert "X-Capture-This-Too" in urllib3_span.data["http"]["header"]
        assert urllib3_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert "X-Capture-That-Too" in urllib3_span.data["http"]["header"]
        assert urllib3_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_extract_custom_headers_exception(
        self, span: "InstanaSpan", caplog: "LogCaptureFixture", monkeypatch
    ) -> None:
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        request_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        monkeypatch.setattr(span, "set_attribute", Exception("mocked error"))
        caplog.set_level(logging.DEBUG, logger="instana")
        extract_custom_headers(span, request_headers)
        assert "extract_custom_headers: " in caplog.messages

    def test_collect_response_exception(
        self, span: "InstanaSpan", caplog: "LogCaptureFixture", monkeypatch
    ) -> None:
        monkeypatch.setattr(span, "set_attribute", Exception("mocked error"))

        caplog.set_level(logging.DEBUG, logger="instana")
        collect_response(span, {})
        assert "urllib3 collect_response error: " in caplog.messages

    def test_collect_kvs_exception(
        self, span: "InstanaSpan", caplog: "LogCaptureFixture", monkeypatch
    ) -> None:
        monkeypatch.setattr(span, "set_attribute", Exception("mocked error"))

        caplog.set_level(logging.DEBUG, logger="instana")
        collect_kvs({}, (), {})
        assert "urllib3 _collect_kvs error: " in caplog.messages
