# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
from typing import Generator, List

from celery import shared_task
import celery
import celery.app
import celery.contrib
import celery.contrib.testing
import celery.contrib.testing.worker
import pytest

from instana.singletons import tracer
from instana.span.span import InstanaSpan
from tests.helpers import get_first_span_by_filter

# TODO: Refactor to class based tests


@shared_task
def add(
    x: int,
    y: int,
) -> int:
    return x + y


@shared_task
def will_raise_error() -> None:
    raise Exception("This is a simulated error")


def filter_out_ping_tasks(
    spans: List[InstanaSpan],
) -> List[InstanaSpan]:
    filtered_spans = []
    for span in spans:
        is_ping_task = (
            span.n == "celery-worker" and span.data["celery"]["task"] == "celery.ping"
        )
        if not is_ping_task:
            filtered_spans.append(span)
    return filtered_spans


class TestCelery:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield

    def test_apply_async(
        self,
        celery_app: celery.app.base.Celery,
        celery_worker: celery.contrib.testing.worker.TestWorkController,
    ) -> None:
        with tracer.start_as_current_span("test"):
            _ = add.apply_async(args=(4, 5))

        # Wait for jobs to finish
        time.sleep(1)

        spans = filter_out_ping_tasks(self.recorder.queued_spans())
        assert len(spans) == 3

        def filter(span):
            return span.n == "sdk"

        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        def filter(span):
            return span.n == "celery-client"

        client_span = get_first_span_by_filter(spans, filter)
        assert client_span

        def filter(span):
            return span.n == "celery-worker"

        worker_span = get_first_span_by_filter(spans, filter)
        assert worker_span

        assert client_span.t == test_span.t
        assert client_span.t == worker_span.t
        assert client_span.p == test_span.s

        assert client_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert client_span.data["celery"]["scheme"] == "redis"
        assert client_span.data["celery"]["host"] == "localhost"
        assert client_span.data["celery"]["port"] == "6379"
        assert client_span.data["celery"]["task_id"]
        assert not client_span.data["celery"]["error"]
        assert not client_span.ec

        assert worker_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert worker_span.data["celery"]["scheme"] == "redis"
        assert worker_span.data["celery"]["host"] == "localhost"
        assert worker_span.data["celery"]["port"] == "6379"
        assert worker_span.data["celery"]["task_id"]
        assert not worker_span.data["celery"]["error"]
        assert not worker_span.data["celery"]["retry-reason"]
        assert not worker_span.ec

    def test_delay(
        self,
        celery_app: celery.app.base.Celery,
        celery_worker: celery.contrib.testing.worker.TestWorkController,
    ) -> None:
        with tracer.start_as_current_span("test"):
            _ = add.delay(4, 5)

        # Wait for jobs to finish
        time.sleep(0.5)

        spans = filter_out_ping_tasks(self.recorder.queued_spans())
        assert len(spans) == 3

        def filter(span):
            return span.n == "sdk"

        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        def filter(span):
            return span.n == "celery-client"

        client_span = get_first_span_by_filter(spans, filter)
        assert client_span

        def filter(span):
            return span.n == "celery-worker"

        worker_span = get_first_span_by_filter(spans, filter)
        assert worker_span

        assert client_span.t == test_span.t
        assert client_span.t == worker_span.t
        assert client_span.p == test_span.s

        assert client_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert client_span.data["celery"]["scheme"] == "redis"
        assert client_span.data["celery"]["host"] == "localhost"
        assert client_span.data["celery"]["port"] == "6379"
        assert client_span.data["celery"]["task_id"]
        assert not client_span.data["celery"]["error"]
        assert not client_span.ec

        assert worker_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert worker_span.data["celery"]["scheme"] == "redis"
        assert worker_span.data["celery"]["host"] == "localhost"
        assert worker_span.data["celery"]["port"] == "6379"
        assert worker_span.data["celery"]["task_id"]
        assert not worker_span.data["celery"]["error"]
        assert not worker_span.data["celery"]["retry-reason"]
        assert not worker_span.ec

    def test_send_task(
        self,
        celery_app: celery.app.base.Celery,
        celery_worker: celery.contrib.testing.worker.TestWorkController,
    ) -> None:
        with tracer.start_as_current_span("test"):
            _ = celery_app.send_task("tests.frameworks.test_celery.add", (1, 2))

        # Wait for jobs to finish
        time.sleep(0.5)

        spans = filter_out_ping_tasks(self.recorder.queued_spans())
        assert len(spans) == 3

        def filter(span):
            return span.n == "sdk"

        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        def filter(span):
            return span.n == "celery-client"

        client_span = get_first_span_by_filter(spans, filter)
        assert client_span

        def filter(span):
            return span.n == "celery-worker"

        worker_span = get_first_span_by_filter(spans, filter)
        assert worker_span

        assert client_span.t == test_span.t
        assert client_span.t == worker_span.t
        assert client_span.p == test_span.s

        assert client_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert client_span.data["celery"]["scheme"] == "redis"
        assert client_span.data["celery"]["host"] == "localhost"
        assert client_span.data["celery"]["port"] == "6379"
        assert client_span.data["celery"]["task_id"]
        assert not client_span.data["celery"]["error"]
        assert not client_span.ec

        assert worker_span.data["celery"]["task"] == "tests.frameworks.test_celery.add"
        assert worker_span.data["celery"]["scheme"] == "redis"
        assert worker_span.data["celery"]["host"] == "localhost"
        assert worker_span.data["celery"]["port"] == "6379"
        assert worker_span.data["celery"]["task_id"]
        assert not worker_span.data["celery"]["error"]
        assert not worker_span.data["celery"]["retry-reason"]
        assert not worker_span.ec

    def test_error_reporting(
        self,
        celery_app: celery.app.base.Celery,
        celery_worker: celery.contrib.testing.worker.TestWorkController,
    ) -> None:
        with tracer.start_as_current_span("test"):
            _ = will_raise_error.apply_async()

        # Wait for jobs to finish
        time.sleep(4)

        spans = filter_out_ping_tasks(self.recorder.queued_spans())
        assert len(spans) == 4

        def filter(span):
            return span.n == "sdk"

        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        def filter(span):
            return span.n == "celery-client"

        client_span = get_first_span_by_filter(spans, filter)
        assert client_span

        def filter(span):
            return span.n == "log"

        log_span = get_first_span_by_filter(spans, filter)
        assert log_span

        def filter(span):
            return span.n == "celery-worker"

        worker_span = get_first_span_by_filter(spans, filter)
        assert worker_span

        assert client_span.t == test_span.t
        assert client_span.t == worker_span.t
        assert client_span.t == log_span.t

        assert client_span.p == test_span.s
        assert worker_span.p == client_span.s
        assert log_span.p == worker_span.s

        assert (
            client_span.data["celery"]["task"]
            == "tests.frameworks.test_celery.will_raise_error"
        )
        assert client_span.data["celery"]["scheme"] == "redis"
        assert client_span.data["celery"]["host"] == "localhost"
        assert client_span.data["celery"]["port"] == "6379"
        assert client_span.data["celery"]["task_id"]
        assert not client_span.data["celery"]["error"]
        assert not client_span.ec

        assert (
            worker_span.data["celery"]["task"]
            == "tests.frameworks.test_celery.will_raise_error"
        )
        assert worker_span.data["celery"]["scheme"] == "redis"
        assert worker_span.data["celery"]["host"] == "localhost"
        assert worker_span.data["celery"]["port"] == "6379"
        assert worker_span.data["celery"]["task_id"]
        assert worker_span.data["celery"]["error"] == "This is a simulated error"
        assert not worker_span.data["celery"]["retry-reason"]
        assert worker_span.ec == 1
