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
        self.rc = redis.StrictRedis.from_url("redis://%s/0" % testenv['redis_url'])

    def tearDown(self):
        pass

    def test_set_get(self):
        result = None
        with tracer.start_active_span('test'):
            self.rc.set('foox', 'barX')
            self.rc.set('fooy', 'barY')
            result = self.rc.get('foox')

        spans = self.recorder.queued_spans()
        self.assertEqual(4, len(spans))

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

        # Redis span
        self.assertEqual('redis', rs1_span.n)
        self.assertFalse('custom' in rs1_span.data.__dict__)
        self.assertTrue('redis' in rs1_span.data.__dict__)

        self.assertEqual('redis-py', rs1_span.data.redis.driver)
        self.assertEqual("redis://%s/0" % testenv['redis_url'], rs1_span.data.redis.connection)

        self.assertIsNotNone(rs1_span.stack)
        self.assertTrue(type(rs1_span.stack) is list)
        self.assertGreater(len(rs1_span.stack), 0)
