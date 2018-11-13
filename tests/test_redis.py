from __future__ import absolute_import

import os
import sys
import unittest

import redis

from .helpers import testenv
from instana.singletons import tracer


class TestRedis(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.strict_redis = redis.StrictRedis.from_url("redis://%s/0" % testenv['redis_url'])
        self.redis = redis.Redis.from_url("redis://%s/0" % testenv['redis_url'])

    def tearDown(self):
        pass

    def test_set_get(self):
        result = None
        with tracer.start_active_span('test'):
            self.strict_redis.set('foox', 'barX')
            self.strict_redis.set('fooy', 'barY')
            result = self.strict_redis.get('foox')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        self.assertEqual(b'barX', result)

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, rs1_span.t)
        self.assertEqual(test_span.t, rs2_span.t)
        self.assertEqual(test_span.t, rs3_span.t)

        # Parent relationships
        self.assertEqual(rs1_span.p, test_span.s)
        self.assertEqual(rs2_span.p, test_span.s)
        self.assertEqual(rs3_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rs1_span.error)
        self.assertIsNone(rs1_span.ec)
        self.assertFalse(rs2_span.error)
        self.assertIsNone(rs2_span.ec)
        self.assertFalse(rs3_span.error)
        self.assertIsNone(rs3_span.ec)

        # Redis span 1
        self.assertEqual('redis', rs1_span.n)
        self.assertFalse('custom' in rs1_span.data.__dict__)
        self.assertTrue('redis' in rs1_span.data.__dict__)

        self.assertEqual('redis-py', rs1_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs1_span.data.redis.connection)
        self.assertEqual("SET", rs1_span.data.redis.command)
        self.assertIsNone(rs1_span.data.redis.error)

        self.assertIsNotNone(rs1_span.stack)
        self.assertTrue(type(rs1_span.stack) is list)
        self.assertGreater(len(rs1_span.stack), 0)

        # Redis span 2
        self.assertEqual('redis', rs2_span.n)
        self.assertFalse('custom' in rs2_span.data.__dict__)
        self.assertTrue('redis' in rs2_span.data.__dict__)

        self.assertEqual('redis-py', rs2_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs2_span.data.redis.connection)
        self.assertEqual("SET", rs2_span.data.redis.command)
        self.assertIsNone(rs2_span.data.redis.error)

        self.assertIsNotNone(rs2_span.stack)
        self.assertTrue(type(rs2_span.stack) is list)
        self.assertGreater(len(rs2_span.stack), 0)

        # Redis span 3
        self.assertEqual('redis', rs3_span.n)
        self.assertFalse('custom' in rs3_span.data.__dict__)
        self.assertTrue('redis' in rs3_span.data.__dict__)

        self.assertEqual('redis-py', rs3_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs3_span.data.redis.connection)
        self.assertEqual("GET", rs3_span.data.redis.command)
        self.assertIsNone(rs3_span.data.redis.error)

        self.assertIsNotNone(rs3_span.stack)
        self.assertTrue(type(rs3_span.stack) is list)
        self.assertGreater(len(rs3_span.stack), 0)

    def test_set_incr_get(self):
        result = None
        with tracer.start_active_span('test'):
            self.strict_redis.set('counter', '10')
            self.strict_redis.incr('counter')
            result = self.strict_redis.get('counter')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        self.assertEqual(b'11', result)

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, rs1_span.t)
        self.assertEqual(test_span.t, rs2_span.t)
        self.assertEqual(test_span.t, rs3_span.t)

        # Parent relationships
        self.assertEqual(rs1_span.p, test_span.s)
        self.assertEqual(rs2_span.p, test_span.s)
        self.assertEqual(rs3_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rs1_span.error)
        self.assertIsNone(rs1_span.ec)
        self.assertFalse(rs2_span.error)
        self.assertIsNone(rs2_span.ec)
        self.assertFalse(rs3_span.error)
        self.assertIsNone(rs3_span.ec)

        # Redis span 1
        self.assertEqual('redis', rs1_span.n)
        self.assertFalse('custom' in rs1_span.data.__dict__)
        self.assertTrue('redis' in rs1_span.data.__dict__)

        self.assertEqual('redis-py', rs1_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs1_span.data.redis.connection)
        self.assertEqual("SET", rs1_span.data.redis.command)
        self.assertIsNone(rs1_span.data.redis.error)

        self.assertIsNotNone(rs1_span.stack)
        self.assertTrue(type(rs1_span.stack) is list)
        self.assertGreater(len(rs1_span.stack), 0)

        # Redis span 2
        self.assertEqual('redis', rs2_span.n)
        self.assertFalse('custom' in rs2_span.data.__dict__)
        self.assertTrue('redis' in rs2_span.data.__dict__)

        self.assertEqual('redis-py', rs2_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs2_span.data.redis.connection)
        self.assertEqual("INCRBY", rs2_span.data.redis.command)
        self.assertIsNone(rs2_span.data.redis.error)

        self.assertIsNotNone(rs2_span.stack)
        self.assertTrue(type(rs2_span.stack) is list)
        self.assertGreater(len(rs2_span.stack), 0)

        # Redis span 3
        self.assertEqual('redis', rs3_span.n)
        self.assertFalse('custom' in rs3_span.data.__dict__)
        self.assertTrue('redis' in rs3_span.data.__dict__)

        self.assertEqual('redis-py', rs3_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs3_span.data.redis.connection)
        self.assertEqual("GET", rs3_span.data.redis.command)
        self.assertIsNone(rs3_span.data.redis.error)

        self.assertIsNotNone(rs3_span.stack)
        self.assertTrue(type(rs3_span.stack) is list)
        self.assertGreater(len(rs3_span.stack), 0)

    def test_old_redis_client(self):
        result = None
        with tracer.start_active_span('test'):
            self.redis.set('foox', 'barX')
            self.redis.set('fooy', 'barY')
            result = self.redis.get('foox')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

        self.assertEqual(b'barX', result)

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, rs1_span.t)
        self.assertEqual(test_span.t, rs2_span.t)
        self.assertEqual(test_span.t, rs3_span.t)

        # Parent relationships
        self.assertEqual(rs1_span.p, test_span.s)
        self.assertEqual(rs2_span.p, test_span.s)
        self.assertEqual(rs3_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rs1_span.error)
        self.assertIsNone(rs1_span.ec)
        self.assertFalse(rs2_span.error)
        self.assertIsNone(rs2_span.ec)
        self.assertFalse(rs3_span.error)
        self.assertIsNone(rs3_span.ec)

        # Redis span 1
        self.assertEqual('redis', rs1_span.n)
        self.assertFalse('custom' in rs1_span.data.__dict__)
        self.assertTrue('redis' in rs1_span.data.__dict__)

        self.assertEqual('redis-py', rs1_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs1_span.data.redis.connection)
        self.assertEqual("SET", rs1_span.data.redis.command)
        self.assertIsNone(rs1_span.data.redis.error)

        self.assertIsNotNone(rs1_span.stack)
        self.assertTrue(type(rs1_span.stack) is list)
        self.assertGreater(len(rs1_span.stack), 0)

        # Redis span 2
        self.assertEqual('redis', rs2_span.n)
        self.assertFalse('custom' in rs2_span.data.__dict__)
        self.assertTrue('redis' in rs2_span.data.__dict__)

        self.assertEqual('redis-py', rs2_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs2_span.data.redis.connection)
        self.assertEqual("SET", rs2_span.data.redis.command)
        self.assertIsNone(rs2_span.data.redis.error)

        self.assertIsNotNone(rs2_span.stack)
        self.assertTrue(type(rs2_span.stack) is list)
        self.assertGreater(len(rs2_span.stack), 0)

        # Redis span 3
        self.assertEqual('redis', rs3_span.n)
        self.assertFalse('custom' in rs3_span.data.__dict__)
        self.assertTrue('redis' in rs3_span.data.__dict__)

        self.assertEqual('redis-py', rs3_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs3_span.data.redis.connection)
        self.assertEqual("GET", rs3_span.data.redis.command)
        self.assertIsNone(rs3_span.data.redis.error)

        self.assertIsNotNone(rs3_span.stack)
        self.assertTrue(type(rs3_span.stack) is list)
        self.assertGreater(len(rs3_span.stack), 0)

    def test_pipelined_requests(self):
        result = None
        with tracer.start_active_span('test'):
            pipe = self.strict_redis.pipeline()
            pipe.set('foox', 'barX')
            pipe.set('fooy', 'barY')
            pipe.get('foox')
            result = pipe.execute()

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        self.assertEqual([True, True, b'barX'], result)

        rs1_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, rs1_span.t)

        # Parent relationships
        self.assertEqual(rs1_span.p, test_span.s)

        # Error logging
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(rs1_span.error)
        self.assertIsNone(rs1_span.ec)

        # Redis span 1
        self.assertEqual('redis', rs1_span.n)
        self.assertFalse('custom' in rs1_span.data.__dict__)
        self.assertTrue('redis' in rs1_span.data.__dict__)

        self.assertEqual('redis-py', rs1_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs1_span.data.redis.connection)
        self.assertEqual("PIPELINE", rs1_span.data.redis.command)
        self.assertEqual(['SET', 'SET', 'GET'], rs1_span.data.redis.subCommands)
        self.assertIsNone(rs1_span.data.redis.error)

        self.assertIsNotNone(rs1_span.stack)
        self.assertTrue(type(rs1_span.stack) is list)
        self.assertGreater(len(rs1_span.stack), 0)
