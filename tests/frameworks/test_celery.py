# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import time
from celery import shared_task
from instana.singletons import tracer
from ..helpers import get_first_span_by_filter


@shared_task
def add(x, y):
    return x + y


@shared_task
def will_raise_error():
    raise Exception('This is a simulated error')


def filter_out_ping_tasks(spans):
    filtered_spans = []
    for span in spans:
        is_ping_task = (span.n == 'celery-worker' and span.data['celery']['task'] == 'celery.ping')
        if not is_ping_task:
            filtered_spans.append(span)
    return filtered_spans


def setup_method():
    """ Clear all spans before a test run """
    tracer.recorder.clear_spans()


def test_apply_async(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = add.apply_async(args=(4, 5))

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = filter_out_ping_tasks(tracer.recorder.queued_spans())
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
    assert("redis" == client_span.data["celery"]["scheme"])
    assert("localhost" == client_span.data["celery"]["host"])
    assert("6379" == client_span.data["celery"]["port"])
    assert(client_span.data["celery"]["task_id"])
    assert(client_span.data["celery"]["error"] == None)
    assert(client_span.ec == None)

    assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
    assert("redis" == worker_span.data["celery"]["scheme"])
    assert("localhost" == worker_span.data["celery"]["host"])
    assert("6379" == worker_span.data["celery"]["port"])
    assert(worker_span.data["celery"]["task_id"])
    assert(worker_span.data["celery"]["error"] == None)
    assert(worker_span.data["celery"]["retry-reason"] == None)
    assert(worker_span.ec == None)


def test_delay(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = add.delay(4, 5)

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = filter_out_ping_tasks(tracer.recorder.queued_spans())
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
    assert("redis" == client_span.data["celery"]["scheme"])
    assert("localhost" == client_span.data["celery"]["host"])
    assert("6379" == client_span.data["celery"]["port"])
    assert(client_span.data["celery"]["task_id"])
    assert(client_span.data["celery"]["error"] == None)
    assert(client_span.ec == None)

    assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
    assert("redis" == worker_span.data["celery"]["scheme"])
    assert("localhost" == worker_span.data["celery"]["host"])
    assert("6379" == worker_span.data["celery"]["port"])
    assert(worker_span.data["celery"]["task_id"])
    assert(worker_span.data["celery"]["error"] == None)
    assert(worker_span.data["celery"]["retry-reason"] == None)
    assert(worker_span.ec == None)


def test_send_task(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = celery_app.send_task('tests.frameworks.test_celery.add', (1, 2))

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = filter_out_ping_tasks(tracer.recorder.queued_spans())
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
    assert("redis" == client_span.data["celery"]["scheme"])
    assert("localhost" == client_span.data["celery"]["host"])
    assert("6379" == client_span.data["celery"]["port"])
    assert(client_span.data["celery"]["task_id"])
    assert(client_span.data["celery"]["error"] == None)
    assert(client_span.ec == None)

    assert("tests.frameworks.test_celery.add" == worker_span.data["celery"]["task"])
    assert("redis" == worker_span.data["celery"]["scheme"])
    assert("localhost" == worker_span.data["celery"]["host"])
    assert("6379" == worker_span.data["celery"]["port"])
    assert(worker_span.data["celery"]["task_id"])
    assert(worker_span.data["celery"]["error"] == None)
    assert(worker_span.data["celery"]["retry-reason"] == None)
    assert(worker_span.ec == None)


def test_error_reporting(celery_app, celery_worker):
    result = None
    with tracer.start_active_span('test'):
        result = will_raise_error.apply_async()

    # Wait for jobs to finish
    time.sleep(0.5)

    spans = filter_out_ping_tasks(tracer.recorder.queued_spans())
    assert len(spans) == 4

    filter = lambda span: span.n == "sdk"
    test_span = get_first_span_by_filter(spans, filter)
    assert(test_span)

    filter = lambda span: span.n == "celery-client"
    client_span = get_first_span_by_filter(spans, filter)
    assert(client_span)

    filter = lambda span: span.n == "log"
    log_span = get_first_span_by_filter(spans, filter)
    assert(log_span)

    filter = lambda span: span.n == "celery-worker"
    worker_span = get_first_span_by_filter(spans, filter)
    assert(worker_span)

    assert(client_span.t == test_span.t)
    assert(client_span.t == worker_span.t)
    assert(client_span.t == log_span.t)

    assert(client_span.p == test_span.s)
    assert(worker_span.p == client_span.s)
    assert(log_span.p == worker_span.s)

    assert("tests.frameworks.test_celery.will_raise_error" == client_span.data["celery"]["task"])
    assert("redis" == client_span.data["celery"]["scheme"])
    assert("localhost" == client_span.data["celery"]["host"])
    assert("6379" == client_span.data["celery"]["port"])
    assert(client_span.data["celery"]["task_id"])
    assert(client_span.data["celery"]["error"] == None)
    assert(client_span.ec == None)

    assert("tests.frameworks.test_celery.will_raise_error" == worker_span.data["celery"]["task"])
    assert("redis" == worker_span.data["celery"]["scheme"])
    assert("localhost" == worker_span.data["celery"]["host"])
    assert("6379" == worker_span.data["celery"]["port"])
    assert(worker_span.data["celery"]["task_id"])
    assert(worker_span.data["celery"]["error"] == 'This is a simulated error')
    assert(worker_span.data["celery"]["retry-reason"] == None)
    assert(worker_span.ec == 1)

