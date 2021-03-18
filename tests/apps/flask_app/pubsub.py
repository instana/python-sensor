import os
import json
import logging

import instana

from flask import Flask, request
from google.auth import jwt
from google.cloud import pubsub_v1

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.debug = True
app.use_reloader = True

# Use PubSub Emulator exposed at :8432 for local testing
# os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8432"

SERVICE_FILE = os.path.join(os.path.dirname(__file__), 'service-account-info.json')
SERVICE_ACCOUNT_INFO = json.load(open(SERVICE_FILE))

AUDIENCE_PUB = "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"
AUDIENCE_SUB = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"

CRED_PUB = jwt.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, audience=AUDIENCE_PUB
)

CRED_SUB = jwt.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, audience=AUDIENCE_SUB
)

PROJECT_ID = 'k8s-brewery'
TOPIC_NAME = 'python-test-topic'
SUBSCRIPTION_ID = 'python-test-subscription'

publisher = pubsub_v1.PublisherClient(credentials=CRED_PUB)
subscriber = pubsub_v1.SubscriberClient(credentials=CRED_SUB)

TOPIC_PATH = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
SUBSCRIPTION_PATH = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)


@app.route('/')
def home():
    return "Welcome to PubSub testing."


@app.route('/create')
def create_topic():
    """
    Usage: /create?topic=<your-topic-name-here>
    """
    topic = request.args.get('topic')
    print(topic, type(topic))

    try:
        publisher.create_topic(TOPIC_PATH)
        return "Topic Created"
    except Exception as e:
        return "Topic Creation Failed: %s" % e


@app.route('/publish')
def publish():
    """
    Usage: /publish?message=<your-message-here>
    """
    msg = request.args.get('message').encode('utf-8')
    publisher.publish(TOPIC_PATH, msg, origin='instana-test')
    return "Published msg: %s" % msg


@app.route('/consume')
def consume():
    """
    Usage: /consume
    * Run it in a different browser tab. Logs on terminal.
    """

    # Async
    def callback_handler(message):
        print('MESSAGE: ', message, type(message))
        print(message.data)
        message.ack()

    future = subscriber.subscribe(SUBSCRIPTION_PATH, callback_handler)

    try:
        res = future.result()
        print('CALLBACK: ', res, type(res))
    except KeyboardInterrupt:
        future.cancel()
    return "Consumer closed."


if __name__ == '__main__':
    app.run(host='127.0.0.1', port='10811')
