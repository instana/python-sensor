from __future__ import absolute_import

import opentracing

from ...singletons import tracer

def inject_trace_context(ctx, task_headers = {}):
    context_headers = {}
    tracer.inject(ctx, opentracing.Format.HTTP_HEADERS, context_headers)

    # Fix for broken header propagation
    # https://github.com/celery/celery/issues/4875
    task_headers.setdefault('headers', {})
    task_headers['headers'].update(context_headers)

    return task_headers
