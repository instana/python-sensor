from __future__ import absolute_import

import time
from celery import shared_task
from instana.singletons import tracer
from ..helpers import get_first_span_by_filter


@shared_task
def add(x, y):
    return x + y


def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()


def test_apply_async(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = add.apply_async(args=(4, 5))

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, filter)
    assert(test_span)

    filter = lambda span: span.n == "celery-client"
    client_span = get_first_span_by_filter(spans, filter)
    assert(client_span)

    filter = lambda span: span.n == "celery-worker"
    worker_span = get_first_span_by_filter(spans, filter)
    assert(worker_span)

    assert(client_span.t == test_span.t)
    assert(client_span.t == worker_span.t)
    assert(client_span.p == test_span.s)

    assert("tests.frameworks.test_celery.add" == client_span.data["celery"]["task"])
    assert("redis://localhost:6379" == client_span.data["celery"]["broker"])
    assert(client_span.data["celery"]["task_id"])

    assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
    assert("redis://localhost:6379" == worker_span.data["celery"]["broker"])
    assert(worker_span.data["celery"]["task_id"])


def test_send_task(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = celery_app.send_task('tests.frameworks.test_celery.add', (1, 2))

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = tracer.recorder.queued_spans()
    assert len(spans) == 3

    filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, filter)
    assert(test_span)

    filter = lambda span: span.n == "celery-client"
    client_span = get_first_span_by_filter(spans, filter)
    assert(client_span)

    filter = lambda span: span.n == "celery-worker"
    worker_span = get_first_span_by_filter(spans, filter)
    assert(worker_span)

    assert(client_span.t == test_span.t)
    assert(client_span.t == worker_span.t)
    assert(client_span.p == test_span.s)

    assert("tests.frameworks.test_celery.add" == client_span.data["celery"]["task"])
    assert("redis://localhost:6379" == client_span.data["celery"]["broker"])
    assert(client_span.data["celery"]["task_id"])

    assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
    assert("redis://localhost:6379" == worker_span.data["celery"]["broker"])
    assert(worker_span.data["celery"]["task_id"])

