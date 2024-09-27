# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

import wrapt

from instana.log import logger
from instana.propagators.format import Format
from instana.singletons import tracer
from instana.util.traceutils import get_tracer_tuple, tracing_is_off

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan

try:
    from google.cloud import pubsub_v1

    def _set_publisher_attributes(
        span: "InstanaSpan",
        topic_path: str,
    ) -> None:
        span.set_attribute("gcps.op", "publish")
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/topic/{topic_name}`
        project_id, topic_name = topic_path.split("/")[1::2]
        span.set_attribute("gcps.projid", project_id)
        span.set_attribute("gcps.top", topic_name)

    def _set_consumer_attributes(
        span: "InstanaSpan",
        subscription_path: str,
    ) -> None:
        span.set_attribute("gcps.op", "consume")
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/subscriptions/{subscription_name}`
        project_id, subscription_id = subscription_path.split("/")[1::2]
        span.set_attribute("gcps.projid", project_id)
        span.set_attribute("gcps.sub", subscription_id)

    @wrapt.patch_function_wrapper("google.cloud.pubsub_v1", "PublisherClient.publish")
    def publish_with_instana(
        wrapped: Callable[..., object],
        instance: pubsub_v1.PublisherClient,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        """References:
        - PublisherClient.publish(topic_path, messages, metadata)
        """
        # return early if we're not tracing
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()
        parent_context = parent_span.get_span_context() if parent_span else None

        with tracer.start_as_current_span(
            "gcps-producer", span_context=parent_context
        ) as span:
            # trace continuity, inject to the span context
            headers = {}
            tracer.inject(
                span.context,
                Format.TEXT_MAP,
                headers,
                disable_w3c_trace_context=True,
            )

            headers = {key: str(value) for key, value in headers.items()}

            # update the metadata dict with instana trace attributes
            kwargs.update(headers)

            _set_publisher_attributes(span, topic_path=args[0])

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as exc:
                span.record_exception(exc)
            else:
                return rv

    @wrapt.patch_function_wrapper(
        "google.cloud.pubsub_v1", "SubscriberClient.subscribe"
    )
    def subscribe_with_instana(
        wrapped: Callable[..., object],
        instance: pubsub_v1.SubscriberClient,
        args: Tuple[object, ...],
        kwargs: Dict[str, Any],
    ) -> object:
        """References:
        - SubscriberClient.subscribe(subscription_path, callback)
        - callback(message) is called from the subscription future
        """

        def callback_with_instana(message):
            if message.attributes:
                parent_context = tracer.extract(
                    Format.TEXT_MAP, message.attributes, disable_w3c_trace_context=True
                )
            else:
                parent_context = None

            with tracer.start_as_current_span(
                "gcps-consumer", span_context=parent_context
            ) as span:
                _set_consumer_attributes(span, subscription_path=args[0])
                try:
                    callback(message)
                except Exception as exc:
                    span.record_exception(exc)

        # Handle callback appropriately from args or kwargs
        if "callback" in kwargs:
            callback = kwargs.get("callback")
            kwargs["callback"] = callback_with_instana
            return wrapped(*args, **kwargs)
        else:
            subscription, callback, *args = args
            args = (subscription, callback_with_instana, *args)
            return wrapped(*args, **kwargs)

    logger.debug("Instrumenting Google Cloud Pub/Sub")
except ImportError:
    pass
