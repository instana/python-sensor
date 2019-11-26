from __future__ import absolute_import

import unittest

import requests
import urllib3

from instana.singletons import tracer
from .helpers import testenv, get_first_span_by_name, get_span_by_filter

from couchbase.bucket import Bucket
from couchbase.exceptions import KeyExistsError, NotFoundError


class TestStandardCouchDB(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.bucket = Bucket('couchbase://mazzo/beer-sample', username='test', password='testtest')

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_get(self):
        res = self.bucket.get("21st_amendment_brewery_cafe")
        self.assertIsNotNone(res)

    def test_pipeline(self):
        pass

    def test_upsert(self):
        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.upsert("test_upsert", 1)

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'upsert')

    def test_insert_new(self):
        res = None
        try:
            self.bucket.remove('test_insert_new')
        except NotFoundError:
            pass

        with tracer.start_active_span('test'):
            res = self.bucket.insert("test_insert_new", 1)

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'insert')

    def test_insert_existing(self):
        res = None
        try:
            self.bucket.insert("test_insert", 1)
        except KeyExistsError:
            pass

        try:
            with tracer.start_active_span('test'):
                res = self.bucket.insert("test_insert", 1)
        except KeyExistsError:
            pass

        self.assertIsNone(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertTrue(cb_span.error)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data.couchbase.error.find("_KeyExistsError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'insert')

    def test_replace(self):
        res = None
        try:
            self.bucket.insert("test_replace", 1)
        except KeyExistsError:
            pass

        with tracer.start_active_span('test'):
            res = self.bucket.replace("test_replace", 2)

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'replace')

    def test_replace_non_existent(self):
        res = None

        try:
            self.bucket.remove("test_replace")
        except NotFoundError:
            pass

        try:
            with tracer.start_active_span('test'):
                res = self.bucket.replace("test_replace", 2)
        except NotFoundError:
            pass

        self.assertIsNone(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertTrue(cb_span.error)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data.couchbase.error.find("NotFoundError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'replace')

    def test_append(self):
        self.bucket.upsert("test_append", "one")

        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.append("test_append", "two")

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'append')

    def test_prepend(self):
        self.bucket.upsert("test_prepend", "one")

        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.prepend("test_prepend", "two")

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'prepend')

    def test_get(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.get("21st_amendment_brewery_cafe")

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'get')

    def test_get_not_found(self):
        res = None
        try:
            self.bucket.remove('test_get_not_found')
        except NotFoundError:
            pass

        try:
            with tracer.start_active_span('test'):
                res = self.bucket.get("test_get_not_found")
        except NotFoundError:
            pass

        self.assertIsNone(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertTrue(cb_span.error)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data.couchbase.error.find("NotFoundError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'get')

    def test_touch(self):
        res = None
        self.bucket.upsert("test_touch", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.touch("test_touch")

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'touch')

    def test_lock(self):
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_active_span('test'):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            self.assertIsNotNone(rv)
            self.assertTrue(rv.success)

            # upsert automatically unlocks the key
            res = self.bucket.upsert("test_lock_unlock", "updated", rv.cas)
            self.assertIsNotNone(res)
            self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        filter = lambda span: span.n == "couchbase" and span.data.couchbase.type == "lock"
        cb_lock_span = get_span_by_filter(spans, filter)
        self.assertIsNotNone(cb_lock_span)

        filter = lambda span: span.n == "couchbase" and span.data.couchbase.type == "upsert"
        cb_upsert_span = get_span_by_filter(spans, filter)
        self.assertIsNotNone(cb_upsert_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_lock_span.t)
        self.assertEqual(test_span.t, cb_upsert_span.t)

        self.assertEqual(cb_lock_span.p, test_span.s)
        self.assertEqual(cb_upsert_span.p, test_span.s)

        self.assertIsNotNone(cb_lock_span.stack)
        self.assertFalse(cb_lock_span.error)
        self.assertIsNone(cb_lock_span.ec)
        self.assertIsNotNone(cb_upsert_span.stack)
        self.assertFalse(cb_upsert_span.error)
        self.assertIsNone(cb_upsert_span.ec)

        self.assertEqual(cb_lock_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_lock_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_lock_span.data.couchbase.type, 'lock')
        self.assertEqual(cb_upsert_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_upsert_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_upsert_span.data.couchbase.type, 'upsert')

    def test_lock_unlock(self):
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_active_span('test'):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            self.assertIsNotNone(rv)
            self.assertTrue(rv.success)

            # upsert automatically unlocks the key
            res = self.bucket.unlock("test_lock_unlock", rv.cas)
            self.assertIsNotNone(res)
            self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        filter = lambda span: span.n == "couchbase" and span.data.couchbase.type == "lock"
        cb_lock_span = get_span_by_filter(spans, filter)
        self.assertIsNotNone(cb_lock_span)

        filter = lambda span: span.n == "couchbase" and span.data.couchbase.type == "unlock"
        cb_unlock_span = get_span_by_filter(spans, filter)
        self.assertIsNotNone(cb_unlock_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_lock_span.t)
        self.assertEqual(test_span.t, cb_unlock_span.t)

        self.assertEqual(cb_lock_span.p, test_span.s)
        self.assertEqual(cb_unlock_span.p, test_span.s)

        self.assertIsNotNone(cb_lock_span.stack)
        self.assertFalse(cb_lock_span.error)
        self.assertIsNone(cb_lock_span.ec)
        self.assertIsNotNone(cb_unlock_span.stack)
        self.assertFalse(cb_unlock_span.error)
        self.assertIsNone(cb_unlock_span.ec)

        self.assertEqual(cb_lock_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_lock_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_lock_span.data.couchbase.type, 'lock')
        self.assertEqual(cb_unlock_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_unlock_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_unlock_span.data.couchbase.type, 'unlock')

    def test_remove(self):
        res = None
        self.bucket.upsert("test_remove", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.remove("test_remove")

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'remove')

    def test_counter(self):
        res = None
        self.bucket.upsert("test_counter", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.counter("test_counter", delta=10)

        self.assertIsNotNone(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        self.assertIsNotNone(test_span)
        self.assertEqual(test_span.data.sdk.name, 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        self.assertIsNotNone(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        self.assertIsNotNone(cb_span.stack)
        self.assertFalse(cb_span.error)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data.couchbase.hostname, 'mazzo:8091')
        self.assertEqual(cb_span.data.couchbase.bucket, 'beer-sample')
        self.assertEqual(cb_span.data.couchbase.type, 'counter')




