# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


import wrapt
from opentracing import Format  # type: ignore

from ....log import logger
from ....singletons import tracer
from ....util.traceutils import get_tracer_tuple, tracing_is_off

try:
    from google.cloud import pubsub_v1  # noqa: F401

    def _set_publisher_tags(span, topic_path):
        span.set_tag("gcps.op", "publish")
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/topic/{topic_name}`
        project_id, topic_name = topic_path.split("/")[1::2]
        span.set_tag("gcps.projid", project_id)
        span.set_tag("gcps.top", topic_name)

    def _set_consumer_tags(span, subscription_path):
        span.set_tag("gcps.op", "consume")
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/subscriptions/{subscription_name}`
        project_id, subscription_id = subscription_path.split("/")[1::2]
        span.set_tag("gcps.projid", project_id)
        span.set_tag("gcps.sub", subscription_id)

    @wrapt.patch_function_wrapper("google.cloud.pubsub_v1", "PublisherClient.publish")
    def publish_with_instana(wrapped, instance, args, kwargs):
        """References:
        - PublisherClient.publish(topic_path, messages, metadata)
        """
        # return early if we're not tracing
        if tracing_is_off():
            return wrapped(*args, **kwargs)

        tracer, parent_span, _ = get_tracer_tuple()

        with tracer.start_active_span("gcps-producer", child_of=parent_span) as scope:
            # trace continuity, inject to the span context
            headers = {}
            tracer.inject(
                scope.span.context,
                Format.TEXT_MAP,
                headers,
                disable_w3c_trace_context=True,
            )

            # update the metadata dict with instana trace attributes
            kwargs.update(headers)

            _set_publisher_tags(scope.span, topic_path=args[0])

            try:
                rv = wrapped(*args, **kwargs)
            except Exception as e:
                scope.span.log_exception(e)
                raise
            else:
                return rv

    @wrapt.patch_function_wrapper(
        "google.cloud.pubsub_v1", "SubscriberClient.subscribe"
    )
    def subscribe_with_instana(wrapped, instance, args, kwargs):
        """References:
        - SubscriberClient.subscribe(subscription_path, callback)
        - callback(message) is called from the subscription future
        """

        def callback_with_instana(message):
            if message.attributes:
                parent_span = tracer.extract(
                    Format.TEXT_MAP, message.attributes, disable_w3c_trace_context=True
                )
            else:
                parent_span = None

            with tracer.start_active_span(
                "gcps-consumer", child_of=parent_span
            ) as scope:
                _set_consumer_tags(scope.span, subscription_path=args[0])
                try:
                    callback(message)
                except Exception as e:
                    scope.span.log_exception(e)
                    raise

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
