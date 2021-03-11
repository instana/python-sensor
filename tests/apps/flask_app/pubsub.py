import json
import logging
import os
from concurrent.futures import TimeoutError
from wsgiref.simple_server import make_server

import instana
from flask import Flask, request
from google.auth import jwt
from google.cloud import pubsub_v1
from instana.singletons import tracer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.debug = True
app.use_reloader = True

SERVICE_ACCOUNT_INFO = json.load(open("service-account-info.json"))
AUDIENCE_PUB = "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"
AUDIENCE_SUB = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"

credentials_pub = jwt.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, audience=AUDIENCE_PUB
)

credentials_sub = jwt.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_INFO, audience=AUDIENCE_SUB
)

publisher = pubsub_v1.PublisherClient(credentials=credentials_pub)
subscriber = pubsub_v1.SubscriberClient(credentials=credentials_sub)

global topic_name

topic_name = f'projects/k8s-brewery/topics/python-test-topic'
project_id = 'k8s-brewery'
subscription_id = 'python-test-subscription'
subscription_path = subscriber.subscription_path(project_id, subscription_id)

@app.route('/')
def home():
    return "Welcome to PubSub testing."

@app.route('/create')
def create_topic():
    topic = request.args.get('topic')
    print(topic, type(topic))
    
    topic_name = f'projects/k8s-brewery/topics/{topic}'
    try: 
        publisher.create_topic(topic_name)
        return "Topic Created"
    except Exception as e:
        return f"Topic Creation Failed: {e}"

@app.route('/publish')
def publish():
    msg = request.args.get('message').encode('utf-8')
    publisher.publish(topic_name, msg, origin='instana-test')
    return f"Published msg: {msg}"

if __name__ == '__main__':
    app.run(host='127.0.0.1', port='10811')