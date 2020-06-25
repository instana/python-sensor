from __future__ import absolute_import

import opentracing
from ...log import logger
from ...singletons import tracer

try:
    import celery
    from celery import registry, signals
    from .catalog import task_catalog_pop, task_catalog_push, get_task_id
    from celery.contrib import rdb

    @signals.task_prerun.connect
    def task_prerun(*args, **kwargs):
        try:
            task = kwargs.get('sender', None)
            task_id = kwargs.get('task_id', None)
            task = registry.tasks.get(task.name)

            #print("task_prerun: %s" % task.name)
            headers = task.request.get('headers', {})
            ctx = tracer.extract(opentracing.Format.HTTP_HEADERS, headers)

            #if task.name == 'tests.test_celery.add':
                #print("task.request: %s" % task.request)
                #print("ctx: %s", ctx)

            if ctx is not None:
                scope = tracer.start_active_span("celery-worker", child_of=ctx)
                scope.span.set_tag("task", task.name)
                scope.span.set_tag("task_id", task_id)
                scope.span.set_tag("broker", task.app.conf['broker_url'])

                # Store the scope on the task to eventually close it out on the "after" signal
                task_catalog_push(task, task_id, scope, True)
        except:
            logger.debug("task_prerun: ", exc_info=True)

    @signals.task_postrun.connect
    def task_postrun(*args, **kwargs):
        try:
            #print("task_postrun")
            task = kwargs.get('sender', None)
            task_id = kwargs.get('task_id', None)
            scope = task_catalog_pop(task, task_id, True)
            if scope is not None:
                scope.close()
        except:
            logger.debug("after_task_publish: ", exc_info=True)

    @signals.before_task_publish.connect
    def before_task_publish(*args, **kwargs):
        try:
            #print("before_task_publish %s" % kwargs['sender'])

            parent_span = tracer.active_span
            if parent_span is not None:
                body = kwargs['body']
                headers = kwargs['headers']
                task_name = kwargs['sender']
                task = registry.tasks.get(task_name)
                task_id = get_task_id(headers, body)

                scope = tracer.start_active_span("celery-client", child_of=parent_span)
                scope.span.set_tag("task", task_name)
                scope.span.set_tag("broker", task.app.conf['broker_url'])
                scope.span.set_tag("task_id", task_id)

                # Context propagation
                context_headers = {}
                tracer.inject(scope.span.context, opentracing.Format.HTTP_HEADERS, context_headers)

                # Fix for broken header propagation
                # https://github.com/celery/celery/issues/4875
                task_headers = kwargs.get('headers') or {}
                task_headers.setdefault('headers', {})
                task_headers['headers'].update(context_headers)
                kwargs['headers'] = task_headers

                # Store the scope on the task to eventually close it out on the "after" signal
                task_catalog_push(task, task_id, scope, False)
        except:
            logger.debug("before_task_publish: ", exc_info=True)

    @signals.after_task_publish.connect
    def after_task_publish(*args, **kwargs):
        try:
            #print("after_task_publish %s" % kwargs['sender'])

            task_id = get_task_id(kwargs['headers'], kwargs['body'])
            task = registry.tasks.get(kwargs['sender'])
            scope = task_catalog_pop(task, task_id, False)
            if scope is not None:
                scope.close()
        except:
            logger.debug("after_task_publish: ", exc_info=True)

    logger.debug("Instrumenting celery client")
except ImportError:
    pass
