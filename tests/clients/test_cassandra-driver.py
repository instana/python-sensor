# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import os
import time
import pytest
import random
import unittest

from instana.singletons import tracer
from ..helpers import testenv, get_first_span_by_name

from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement

cluster = Cluster([testenv['cassandra_host']], load_balancing_policy=None)
session = cluster.connect()

session.execute("CREATE KEYSPACE IF NOT EXISTS instana_tests WITH replication = {'class':'SimpleStrategy', 'replication_factor':1};")
session.set_keyspace('instana_tests')
session.execute("CREATE TABLE IF NOT EXISTS users("
                "id int PRIMARY KEY,"
                "name text,"
                "age text,"
                "email varint,"
                "phone varint"
                ");")


@pytest.mark.skipif("CASSANDRA_TEST" not in os.environ, reason="")
class TestCassandra(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_untraced_execute(self):
        res = session.execute('SELECT name, age, email FROM users')

        self.assertIsNotNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_untraced_execute_error(self):
        res = None
        try:
            res = session.execute('Not a valid query')
        except:
            pass

        self.assertIsNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_execute(self):
        res = None
        with tracer.start_active_span('test'):
            res = session.execute('SELECT name, age, email FROM users')

        self.assertIsNotNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cspan = get_first_span_by_name(spans, 'cassandra')
        self.assertIsNotNone(cspan)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cspan.t)
        self.assertEqual(cspan.p, test_span.s)

        self.assertIsNotNone(cspan.stack)
        self.assertIsNone(cspan.ec)

        self.assertEqual(cspan.data["cassandra"]["cluster"], 'Test Cluster')
        self.assertEqual(cspan.data["cassandra"]["query"], 'SELECT name, age, email FROM users')
        self.assertEqual(cspan.data["cassandra"]["keyspace"], 'instana_tests')
        self.assertIsNone(cspan.data["cassandra"]["achievedConsistency"])
        self.assertIsNotNone(cspan.data["cassandra"]["triedHosts"])
        self.assertIsNone(cspan.data["cassandra"]["error"])

    def test_execute_async(self):
        res = None
        with tracer.start_active_span('test'):
            res = session.execute_async('SELECT name, age, email FROM users').result()

        self.assertIsNotNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cspan = get_first_span_by_name(spans, 'cassandra')
        self.assertIsNotNone(cspan)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cspan.t)
        self.assertEqual(cspan.p, test_span.s)

        self.assertIsNotNone(cspan.stack)
        self.assertIsNone(cspan.ec)

        self.assertEqual(cspan.data["cassandra"]["cluster"], 'Test Cluster')
        self.assertEqual(cspan.data["cassandra"]["query"], 'SELECT name, age, email FROM users')
        self.assertEqual(cspan.data["cassandra"]["keyspace"], 'instana_tests')
        self.assertIsNone(cspan.data["cassandra"]["achievedConsistency"])
        self.assertIsNotNone(cspan.data["cassandra"]["triedHosts"])
        self.assertIsNone(cspan.data["cassandra"]["error"])

    def test_simple_statement(self):
        res = None
        with tracer.start_active_span('test'):
            query = SimpleStatement(
                'SELECT name, age, email FROM users',
                is_idempotent=True
            )
            res = session.execute(query)

        self.assertIsNotNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cspan = get_first_span_by_name(spans, 'cassandra')
        self.assertIsNotNone(cspan)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cspan.t)
        self.assertEqual(cspan.p, test_span.s)

        self.assertIsNotNone(cspan.stack)
        self.assertIsNone(cspan.ec)

        self.assertEqual(cspan.data["cassandra"]["cluster"], 'Test Cluster')
        self.assertEqual(cspan.data["cassandra"]["query"], 'SELECT name, age, email FROM users')
        self.assertEqual(cspan.data["cassandra"]["keyspace"], 'instana_tests')
        self.assertIsNone(cspan.data["cassandra"]["achievedConsistency"])
        self.assertIsNotNone(cspan.data["cassandra"]["triedHosts"])
        self.assertIsNone(cspan.data["cassandra"]["error"])

    def test_execute_error(self):
        res = None

        try:
            with tracer.start_active_span('test'):
                res = session.execute('Not a real query')
        except:
            pass

        self.assertIsNone(res)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cspan = get_first_span_by_name(spans, 'cassandra')
        self.assertIsNotNone(cspan)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cspan.t)
        self.assertEqual(cspan.p, test_span.s)

        self.assertIsNotNone(cspan.stack)
        self.assertEqual(cspan.ec, 1)

        self.assertEqual(cspan.data["cassandra"]["cluster"], 'Test Cluster')
        self.assertEqual(cspan.data["cassandra"]["query"], 'Not a real query')
        self.assertEqual(cspan.data["cassandra"]["keyspace"], 'instana_tests')
        self.assertIsNone(cspan.data["cassandra"]["achievedConsistency"])
        self.assertIsNotNone(cspan.data["cassandra"]["triedHosts"])
        self.assertIsNotNone(cspan.data["cassandra"]["error"])

    def test_prepared_statement(self):
        prepared = None
        result = None

        with tracer.start_active_span('test'):
            prepared = session.prepare('INSERT INTO users (id, name, age) VALUES (?, ?, ?)')
            prepared.consistency_level = ConsistencyLevel.QUORUM
            result = session.execute(prepared, (random.randint(0, 1000000), "joe", "17"))

        self.assertIsNotNone(prepared)
        self.assertIsNotNone(result)

        time.sleep(0.5)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cspan = get_first_span_by_name(spans, 'cassandra')
        self.assertIsNotNone(cspan)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cspan.t)
        self.assertEqual(cspan.p, test_span.s)

        self.assertIsNotNone(cspan.stack)
        self.assertIsNone(cspan.ec)

        self.assertEqual(cspan.data["cassandra"]["cluster"], 'Test Cluster')
        self.assertEqual(cspan.data["cassandra"]["query"], 'INSERT INTO users (id, name, age) VALUES (?, ?, ?)')
        self.assertEqual(cspan.data["cassandra"]["keyspace"], 'instana_tests')
        self.assertEqual(cspan.data["cassandra"]["achievedConsistency"], "QUORUM")
        self.assertIsNotNone(cspan.data["cassandra"]["triedHosts"])
        self.assertIsNone(cspan.data["cassandra"]["error"])
