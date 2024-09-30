# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import random
import time
from typing import Generator

import pytest
from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster, ResultSet
from cassandra.query import SimpleStatement

from instana.singletons import agent, tracer
from tests.helpers import get_first_span_by_name, testenv

cluster = Cluster([testenv["cassandra_host"]], load_balancing_policy=None)
session = cluster.connect()

session.execute(
    "CREATE KEYSPACE IF NOT EXISTS instana_tests WITH replication = {'class':'SimpleStrategy', 'replication_factor':1};"
)
session.set_keyspace("instana_tests")
session.execute(
    "CREATE TABLE IF NOT EXISTS users("
    "id int PRIMARY KEY,"
    "name text,"
    "age text,"
    "email varint,"
    "phone varint"
    ");"
)


class TestCassandra:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield
        agent.options.allow_exit_as_root = False

    def test_untraced_execute(self) -> None:
        res = session.execute("SELECT name, age, email FROM users")

        assert isinstance(res, ResultSet)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_untraced_execute_error(self) -> None:
        res = None
        try:
            res = session.execute("Not a valid query")
        except Exception:
            pass

        assert not res

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_execute(self) -> None:
        res = None
        with tracer.start_as_current_span("test"):
            res = session.execute("SELECT name, age, email FROM users")

        assert isinstance(res, ResultSet)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        # Same traceId and parent relationship
        assert cspan.t == test_span.t
        assert cspan.p == test_span.s

        assert cspan.stack
        assert not cspan.ec

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert cspan.data["cassandra"]["query"] == "SELECT name, age, email FROM users"
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert not cspan.data["cassandra"]["achievedConsistency"]
        assert cspan.data["cassandra"]["triedHosts"]
        assert not cspan.data["cassandra"]["error"]

    def test_execute_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        res = session.execute("SELECT name, age, email FROM users")

        assert isinstance(res, ResultSet)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        assert not cspan.p

        assert cspan.stack
        assert not cspan.ec

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert cspan.data["cassandra"]["query"] == "SELECT name, age, email FROM users"
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert not cspan.data["cassandra"]["achievedConsistency"]
        assert cspan.data["cassandra"]["triedHosts"]
        assert not cspan.data["cassandra"]["error"]

    def test_execute_async(self) -> None:
        res = None
        with tracer.start_as_current_span("test"):
            res = session.execute_async("SELECT name, age, email FROM users").result()

        assert isinstance(res, ResultSet)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        # Same traceId and parent relationship
        assert cspan.t == test_span.t
        assert cspan.p == test_span.s

        assert cspan.stack
        assert not cspan.ec

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert cspan.data["cassandra"]["query"] == "SELECT name, age, email FROM users"
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert not cspan.data["cassandra"]["achievedConsistency"]
        assert cspan.data["cassandra"]["triedHosts"]
        assert not cspan.data["cassandra"]["error"]

    def test_simple_statement(self) -> None:
        res = None
        with tracer.start_as_current_span("test"):
            query = SimpleStatement(
                "SELECT name, age, email FROM users", is_idempotent=True
            )
            res = session.execute(query)

        assert isinstance(res, ResultSet)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        # Same traceId and parent relationship
        assert cspan.t == test_span.t
        assert cspan.p == test_span.s

        assert cspan.stack
        assert not cspan.ec

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert cspan.data["cassandra"]["query"] == "SELECT name, age, email FROM users"
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert not cspan.data["cassandra"]["achievedConsistency"]
        assert cspan.data["cassandra"]["triedHosts"]
        assert not cspan.data["cassandra"]["error"]

    def test_execute_error(self) -> None:
        res = None

        try:
            with tracer.start_as_current_span("test"):
                res = session.execute("Not a real query")
        except Exception:
            pass

        assert not res

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        # Same traceId and parent relationship
        assert cspan.t == test_span.t
        assert cspan.p == test_span.s

        assert cspan.stack
        assert cspan.ec == 1

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert cspan.data["cassandra"]["query"] == "Not a real query"
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert not cspan.data["cassandra"]["achievedConsistency"]
        assert cspan.data["cassandra"]["triedHosts"]
        assert cspan.data["cassandra"]["error"] == "Syntax error in CQL query"

    def test_prepared_statement(self) -> None:
        prepared = None

        with tracer.start_as_current_span("test"):
            prepared = session.prepare(
                "INSERT INTO users (id, name, age) VALUES (?, ?, ?)"
            )
            prepared.consistency_level = ConsistencyLevel.QUORUM
            session.execute(prepared, (random.randint(0, 1000000), "joe", "17"))

        assert prepared

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cspan = get_first_span_by_name(spans, "cassandra")
        assert cspan

        # Same traceId and parent relationship
        assert test_span.t == cspan.t
        assert cspan.p == test_span.s

        assert cspan.stack
        assert not cspan.ec

        assert cspan.data["cassandra"]["cluster"] == "Test Cluster"
        assert (
            cspan.data["cassandra"]["query"]
            == "INSERT INTO users (id, name, age) VALUES (?, ?, ?)"
        )
        assert cspan.data["cassandra"]["keyspace"] == "instana_tests"
        assert cspan.data["cassandra"]["achievedConsistency"] == "QUORUM"
        assert cspan.data["cassandra"]["triedHosts"]
        assert not cspan.data["cassandra"]["error"]
