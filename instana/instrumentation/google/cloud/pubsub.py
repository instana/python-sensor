# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import json
import wrapt
from opentracing import Format

from ....log import logger
from ....singletons import tracer

try:
    from google.cloud import pubsub_v1


    def _set_publisher_tags(span, topic_path):
        span.set_tag('gcps.op', 'publish')
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/topic/{topic_name}`
        project_id, topic_name = topic_path.split('/')[1::2]
        span.set_tag('gcps.projid', project_id)
        span.set_tag('gcps.top', topic_name)


    def _set_consumer_tags(span, subscription_path):
        span.set_tag('gcps.op', 'consume')
        # Fully qualified identifier is in the form of
        # `projects/{project_id}/subscriptions/{subscription_name}`
        project_id, subscription_id = subscription_path.split('/')[1::2]
        span.set_tag('gcps.projid', project_id)
        span.set_tag('gcps.sub', subscription_id)


    @wrapt.patch_function_wrapper('google.cloud.pubsub_v1', 'PublisherClient.publish')
    def publish_with_instana(wrapped, instance, args, kwargs):
        """References:
        - PublisherClient.publish(topic_path, messages, metadata)
        """
        # check if active
        parent_span = tracer.active_span

        # return early if we're not tracing
        if parent_span is None:
            return wrapped(*args, **kwargs)

        with tracer.start_active_span('gcps-producer', child_of=parent_span) as scope:
            # trace continuity, inject to the span context
            headers = dict()
            tracer.inject(scope.span.context, Format.TEXT_MAP, headers)

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


    @wrapt.patch_function_wrapper('google.cloud.pubsub_v1', 'SubscriberClient.subscribe')
    def subscribe_with_instana(wrapped, instance, args, kwargs):

        """References:
        - SubscriberClient.subscribe(subscription_path, callback)
        - callback(message) is called from the subscription future
        """

        def callback_with_instana(message):
            if message.attributes:
                parent_span = tracer.extract(Format.TEXT_MAP, message.attributes)
            else:
                parent_span = None

            with tracer.start_active_span('gcps-consumer', child_of=parent_span) as scope:
                _set_consumer_tags(scope.span, subscription_path=args[0])
                try:
                    callback(message)
                except Exception as e:
                    scope.span.log_exception(e)
                    raise

        # Handle callback appropriately from args or kwargs
        if 'callback' in kwargs:
            callback = kwargs.get('callback')
            kwargs['callback'] = callback_with_instana
            return wrapped(*args, **kwargs)
        else:
            subscription, callback, *args = args
            args = (subscription, callback_with_instana, *args)
            return wrapped(*args, **kwargs)


    logger.debug('Instrumenting Google Cloud Pub/Sub')
except ImportError:
    pass
