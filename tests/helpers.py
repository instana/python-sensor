# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import os

import pytest

testenv = {}

"""
Cassandra Environment
"""
testenv["cassandra_host"] = os.environ.get("CASSANDRA_HOST", "127.0.0.1")
testenv["cassandra_username"] = os.environ.get("CASSANDRA_USERNAME", "Administrator")
testenv["cassandra_password"] = os.environ.get("CASSANDRA_PASSWORD", "password")

"""
CouchDB Environment
"""
testenv["couchdb_host"] = os.environ.get("COUCHDB_HOST", "127.0.0.1")
testenv["couchdb_username"] = os.environ.get("COUCHDB_USERNAME", "Administrator")
testenv["couchdb_password"] = os.environ.get("COUCHDB_PASSWORD", "password")

"""
MySQL Environment
"""
if "MYSQL_HOST" in os.environ:
    testenv["mysql_host"] = os.environ["MYSQL_HOST"]
else:
    testenv["mysql_host"] = "127.0.0.1"

testenv["mysql_port"] = int(os.environ.get("MYSQL_PORT", "3306"))
testenv["mysql_db"] = os.environ.get("MYSQL_DATABASE", "instana_test_db")
testenv["mysql_user"] = os.environ.get("MYSQL_USER", "root")
testenv["mysql_pw"] = os.environ.get("MYSQL_ROOT_PASSWORD", "passw0rd")

"""
PostgreSQL Environment
"""
testenv["postgresql_host"] = os.environ.get("POSTGRES_HOST", "127.0.0.1")
testenv["postgresql_port"] = int(os.environ.get("POSTGRES_PORT", "5432"))
testenv["postgresql_db"] = os.environ.get("POSTGRES_DB", "instana_test_db")
testenv["postgresql_user"] = os.environ.get("POSTGRES_USER", "root")
testenv["postgresql_pw"] = os.environ.get("POSTGRES_PW", "passw0rd")

"""
Redis Environment
"""
testenv["redis_host"] = os.environ.get("REDIS_HOST", "127.0.0.1")
testenv["redis_db"] = os.environ.get("REDIS_DB", 0)

"""
MongoDB Environment
"""
testenv["mongodb_host"] = os.environ.get("MONGO_HOST", "127.0.0.1")
testenv["mongodb_port"] = os.environ.get("MONGO_PORT", "27017")
testenv["mongodb_user"] = os.environ.get("MONGO_USER", None)
testenv["mongodb_pw"] = os.environ.get("MONGO_PW", None)

"""
RabbitMQ Environment
"""
testenv["rabbitmq_host"] = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
testenv["rabbitmq_port"] = os.environ.get("RABBITMQ_PORT", 5672)


"""
Kafka Environment
"""
testenv["kafka_host"] = os.environ.get("KAFKA_HOST", "127.0.0.1")
testenv["kafka_port"] = os.environ.get("KAFKA_PORT", "9094")
testenv["kafka_topic"] = os.environ.get("KAFKA_TOPIC", "span-topic")
testenv["kafka_bootstrap_servers"] = [
    f"{testenv['kafka_host']}:{testenv['kafka_port']}",
]


def drop_log_spans_from_list(spans):
    """
    Log spans may occur randomly in test runs because of various intentional errors (for testing). This
    helper method will remove all of the log spans from <spans> and return the remaining list.  Helpful
    for those tests where we are not testing log spans - where log spans are just noise.
    @param spans: the list of spans to filter
    @return: a filtered list of spans
    """
    new_list = []
    for span in spans:
        if span.n != "log":
            new_list.append(span)
    return new_list


def fail_with_message_and_span_dump(msg, spans):
    """
    Helper method to fail a test when the number of spans isn't what was expected.  This helper
    will print <msg> and dump the list of spans in <spans>.

    @param msg: Descriptive message to print with the failure
    @param spans: the list of spans to dump
    @return: None
    """
    span_count = len(spans)
    span_dump = "\nDumping all collected spans (%d) -->\n" % span_count
    if span_count > 0:
        for span in spans:
            span.stack = "<snipped>"
            span_dump += repr(span) + "\n"
    pytest.fail(msg + span_dump, True)


def is_test_span(span):
    """
    return the filter for test span
    """
    return span.n == "sdk" and span.data["sdk"]["name"] == "test"

def get_first_span_by_name(spans, name):
    """
    Get the first span in <spans> that has a span.n value of <name>
    @param spans: the list of spans to search
    @param name: the name to search for
    @return: Span or None if nothing found
    """
    for span in spans:
        if span.n == name:
            return span
    return None


def get_first_span_by_filter(spans, filter):
    """
    Get the first span in <spans> that matches <filter>

    Example:
    filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 301
    tornado_301_span = get_first_span_by_filter(spans, filter)

    @param spans: the list of spans to search
    @param filter: the filter to search by
    @return: Span or None if nothing matched
    """
    for span in spans:
        if filter(span) is True:
            return span
    return None


def get_spans_by_filter(spans, filter):
    """
    Get all spans in <spans> that matches <filter>

    Example:
    filter = lambda span: span.n == "tornado-server" and span.data["http"]["status"] == 301
    tornado_301_spans = get_spans_by_filter(spans, filter)

    @param spans: the list of spans to search
    @param filter: the filter to search by
    @return: list of spans
    """
    results = []
    for span in spans:
        if filter(span) is True:
            results.append(span)
    return results


def launch_traced_request(url):
    import requests

    from instana.log import logger
    from instana.singletons import tracer

    logger.warn(
        "Launching request with a root SDK span name of 'launch_traced_request'"
    )

    with tracer.start_as_current_span("launch_traced_request"):
        response = requests.get(url)

    return response
