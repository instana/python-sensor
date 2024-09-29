# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import contextvars
from typing import Any, Dict, Tuple
from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import tracer
from instana.span.span import InstanaSpan
from instana.util.traceutils import get_tracer_tuple
from opentelemetry import trace, context

try:
    import celery
    from celery import registry, signals

    from urllib import parse

    client_token: Dict[str, Any] = {}
    worker_token: Dict[str, Any] = {}
    client_span = contextvars.ContextVar("client_span")
    worker_span = contextvars.ContextVar("worker_span")

    def _get_task_id(
        headers: Dict[str, Any],
        body: Tuple[str, Any],
    ) -> str:
        """
        Across Celery versions, the task id can exist in a couple of places.
        """
        id = headers.get("id", None)
        if id is None:
            id = body.get("id", None)
        return id

    def add_broker_attributes(
        span: InstanaSpan,
        broker_url: str,
    ) -> None:
        try:
            url = parse.urlparse(broker_url)

            # Add safety for edge case where scheme may not be a string
            url_scheme = str(url.scheme)
            span.set_attribute("scheme", url_scheme)

            span.set_attribute("host", url.hostname if url.hostname else "localhost")

            if not url.port:
                # Set default port if not specified
                if url_scheme == "redis":
                    span.set_attribute("port", "6379")
                elif "amqp" in url_scheme:
                    span.set_attribute("port", "5672")
                elif "sqs" in url_scheme:
                    span.set_attribute("port", "443")
            else:
                span.set_attribute("port", str(url.port))
        except Exception:
            logger.debug(f"Error parsing broker URL: {broker_url}", exc_info=True)

    @signals.task_prerun.connect
    def task_prerun(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            ctx = None

            task = kwargs.get("sender", None)
            task_id = kwargs.get("task_id", None)
            task = registry.tasks.get(task.name)

            headers = task.request.get("headers", {})
            if headers is not None:
                ctx = tracer.extract(
                    Format.HTTP_HEADERS, headers, disable_w3c_trace_context=True
                )

            span = tracer.start_span("celery-worker", span_context=ctx)
            span.set_attribute("task", task.name)
            span.set_attribute("task_id", task_id)
            add_broker_attributes(span, task.app.conf["broker_url"])

            ctx = trace.set_span_in_context(span)
            token = context.attach(ctx)
            worker_token["token"] = token
            worker_span.set(span)
        except Exception:
            logger.debug("celery-worker task_prerun: ", exc_info=True)

    @signals.task_postrun.connect
    def task_postrun(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            span = worker_span.get()

            if span.is_recording():
                span.end()
                worker_span.set(None)
            if "token" in worker_token:
                context.detach(worker_token.pop("token", None))
        except Exception:
            logger.debug("celery-worker after_task_publish: ", exc_info=True)

    @signals.task_failure.connect
    def task_failure(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            span = worker_span.get()
            if span.is_recording():
                span.set_attribute("success", False)
                exc = kwargs.get("exception", None)
                if exc:
                    span.record_exception(exc)
                else:
                    span.mark_as_errored()
        except Exception:
            logger.debug("celery-worker task_failure: ", exc_info=True)

    @signals.task_retry.connect
    def task_retry(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            span = worker_span.get()
            if span.is_recording():
                reason = kwargs.get("reason", None)
                if reason:
                    span.set_attribute("retry-reason", reason)
        except Exception:
            logger.debug("celery-worker task_failure: ", exc_info=True)

    @signals.before_task_publish.connect
    def before_task_publish(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            tracer, parent_span, _ = get_tracer_tuple()
            parent_context = parent_span.get_span_context() if parent_span else None

            if tracer:
                body = kwargs["body"]
                headers = kwargs["headers"]
                task_name = kwargs["sender"]
                task = registry.tasks.get(task_name)
                task_id = _get_task_id(headers, body)

                span = tracer.start_span("celery-client", span_context=parent_context)
                span.set_attribute("task", task_name)
                span.set_attribute("task_id", task_id)
                add_broker_attributes(span, task.app.conf["broker_url"])

                # Context propagation
                context_headers = {}
                tracer.inject(
                    span.context,
                    Format.HTTP_HEADERS,
                    context_headers,
                    disable_w3c_trace_context=True,
                )

                # Fix for broken header propagation
                # https://github.com/celery/celery/issues/4875
                task_headers = kwargs.get("headers") or {}
                task_headers.setdefault("headers", {})
                task_headers["headers"].update(context_headers)
                kwargs["headers"] = task_headers

                ctx = trace.set_span_in_context(span)
                token = context.attach(ctx)
                client_token["token"] = token
                client_span.set(span)
        except Exception:
            logger.debug("celery-client before_task_publish: ", exc_info=True)

    @signals.after_task_publish.connect
    def after_task_publish(
        *args: Tuple[object, ...],
        **kwargs: Dict[str, Any],
    ) -> None:
        try:
            span = client_span.get()
            if span.is_recording():
                span.end()
                client_span.set(None)
            if "token" in client_token:
                context.detach(client_token.pop("token", None))

        except Exception:
            logger.debug("celery-client after_task_publish: ", exc_info=True)

    logger.debug("Instrumenting celery")
except ImportError:
    pass
