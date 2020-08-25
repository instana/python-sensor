from __future__ import absolute_import

import time
import pytest
import unittest

from instana.singletons import tracer
from ..helpers import testenv, get_first_span_by_name, get_first_span_by_filter

from couchbase.admin import Admin
from couchbase.cluster import Cluster
from couchbase.bucket import Bucket
from couchbase.exceptions import CouchbaseTransientError, HTTPError, KeyExistsError, NotFoundError
import couchbase.subdocument as SD
from couchbase.n1ql import N1QLQuery

# Delete any pre-existing buckets.  Create new.
cb_adm = Admin(testenv['couchdb_username'], testenv['couchdb_password'], host=testenv['couchdb_host'], port=8091)

# Make sure a test bucket exists
try:
    cb_adm.bucket_create('travel-sample')
    cb_adm.wait_ready('travel-sample', timeout=30)
except HTTPError:
    pass


@pytest.mark.skipif("COUCHBASE_TEST" not in os.environ, reason="")
class TestStandardCouchDB(unittest.TestCase):
    def setup_class(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.cluster = Cluster('couchbase://%s' % testenv['couchdb_host'])
        self.bucket = Bucket('couchbase://%s/travel-sample' % testenv['couchdb_host'],
                             username=testenv['couchdb_username'], password=testenv['couchdb_password'])

    def setup_method(self):
        self.bucket.upsert('test-key', 1)
        time.sleep(0.5)
        self.recorder.clear_spans()

    def test_vanilla_get(self):
        res = self.bucket.get("test-key")
        assert(res)

    def test_pipeline(self):
        pass

    def test_upsert(self):
        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.upsert("test_upsert", 1)

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'upsert')

    def test_upsert_multi(self):
        res = None

        kvs = dict()
        kvs['first_test_upsert_multi'] = 1
        kvs['second_test_upsert_multi'] = 1

        with tracer.start_active_span('test'):
            res = self.bucket.upsert_multi(kvs)

        assert(res)
        self.assertTrue(res['first_test_upsert_multi'].success)
        self.assertTrue(res['second_test_upsert_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'upsert_multi')

    def test_insert_new(self):
        res = None
        try:
            self.bucket.remove('test_insert_new')
        except NotFoundError:
            pass

        with tracer.start_active_span('test'):
            res = self.bucket.insert("test_insert_new", 1)

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'insert')

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
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("_KeyExistsError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'insert')

    def test_insert_multi(self):
        res = None

        kvs = dict()
        kvs['first_test_upsert_multi'] = 1
        kvs['second_test_upsert_multi'] = 1

        try:
            self.bucket.remove('first_test_upsert_multi')
            self.bucket.remove('second_test_upsert_multi')
        except NotFoundError:
            pass

        with tracer.start_active_span('test'):
            res = self.bucket.insert_multi(kvs)

        assert(res)
        self.assertTrue(res['first_test_upsert_multi'].success)
        self.assertTrue(res['second_test_upsert_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'insert_multi')

    def test_replace(self):
        res = None
        try:
            self.bucket.insert("test_replace", 1)
        except KeyExistsError:
            pass

        with tracer.start_active_span('test'):
            res = self.bucket.replace("test_replace", 2)

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'replace')

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
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("NotFoundError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'replace')

    def test_replace_multi(self):
        res = None

        kvs = dict()
        kvs['first_test_replace_multi'] = 1
        kvs['second_test_replace_multi'] = 1

        self.bucket.upsert('first_test_replace_multi', "one")
        self.bucket.upsert('second_test_replace_multi', "two")

        with tracer.start_active_span('test'):
            res = self.bucket.replace_multi(kvs)

        assert(res)
        self.assertTrue(res['first_test_replace_multi'].success)
        self.assertTrue(res['second_test_replace_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'replace_multi')

    def test_append(self):
        self.bucket.upsert("test_append", "one")

        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.append("test_append", "two")

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'append')

    def test_append_multi(self):
        res = None

        kvs = dict()
        kvs['first_test_append_multi'] = "ok1"
        kvs['second_test_append_multi'] = "ok2"

        self.bucket.upsert('first_test_append_multi', "one")
        self.bucket.upsert('second_test_append_multi', "two")

        with tracer.start_active_span('test'):
            res = self.bucket.append_multi(kvs)

        assert(res)
        self.assertTrue(res['first_test_append_multi'].success)
        self.assertTrue(res['second_test_append_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'append_multi')

    def test_prepend(self):
        self.bucket.upsert("test_prepend", "one")

        res = None
        with tracer.start_active_span('test'):
            res = self.bucket.prepend("test_prepend", "two")

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'prepend')

    def test_prepend_multi(self):
        res = None

        kvs = dict()
        kvs['first_test_prepend_multi'] = "ok1"
        kvs['second_test_prepend_multi'] = "ok2"

        self.bucket.upsert('first_test_prepend_multi', "one")
        self.bucket.upsert('second_test_prepend_multi', "two")

        with tracer.start_active_span('test'):
            res = self.bucket.prepend_multi(kvs)

        assert(res)
        self.assertTrue(res['first_test_prepend_multi'].success)
        self.assertTrue(res['second_test_prepend_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'prepend_multi')

    def test_get(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.get("test-key")

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'get')

    def test_rget(self):
        res = None

        try:
            with tracer.start_active_span('test'):
                res = self.bucket.rget("test-key", replica_index=None)
        except CouchbaseTransientError:
            pass

        self.assertIsNone(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("CouchbaseTransientError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'rget')

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
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertEqual(cb_span.ec, 1)
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("NotFoundError")
        self.assertFalse(found == -1, "Error substring not found.")

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'get')

    def test_get_multi(self):
        res = None

        self.bucket.upsert('first_test_get_multi', "one")
        self.bucket.upsert('second_test_get_multi', "two")

        with tracer.start_active_span('test'):
            res = self.bucket.get_multi(['first_test_get_multi', 'second_test_get_multi'])

        assert(res)
        self.assertTrue(res['first_test_get_multi'].success)
        self.assertTrue(res['second_test_get_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'get_multi')

    def test_touch(self):
        res = None
        self.bucket.upsert("test_touch", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.touch("test_touch")

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'touch')

    def test_touch_multi(self):
        res = None

        self.bucket.upsert('first_test_touch_multi', "one")
        self.bucket.upsert('second_test_touch_multi', "two")

        with tracer.start_active_span('test'):
            res = self.bucket.touch_multi(['first_test_touch_multi', 'second_test_touch_multi'])

        assert(res)
        self.assertTrue(res['first_test_touch_multi'].success)
        self.assertTrue(res['second_test_touch_multi'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'touch_multi')

    def test_lock(self):
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_active_span('test'):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            assert(rv)
            self.assertTrue(rv.success)

            # upsert automatically unlocks the key
            res = self.bucket.upsert("test_lock_unlock", "updated", rv.cas)
            assert(res)
            self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "lock"
        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert(cb_lock_span)

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "upsert"
        cb_upsert_span = get_first_span_by_filter(spans, filter)
        assert(cb_upsert_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_lock_span.t)
        self.assertEqual(test_span.t, cb_upsert_span.t)

        self.assertEqual(cb_lock_span.p, test_span.s)
        self.assertEqual(cb_upsert_span.p, test_span.s)

        assert(cb_lock_span.stack)
        self.assertIsNone(cb_lock_span.ec)
        assert(cb_upsert_span.stack)
        self.assertIsNone(cb_upsert_span.ec)

        self.assertEqual(cb_lock_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_lock_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_lock_span.data["couchbase"]["type"], 'lock')
        self.assertEqual(cb_upsert_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_upsert_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_upsert_span.data["couchbase"]["type"], 'upsert')

    def test_lock_unlock(self):
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_active_span('test'):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            assert(rv)
            self.assertTrue(rv.success)

            # upsert automatically unlocks the key
            res = self.bucket.unlock("test_lock_unlock", rv.cas)
            assert(res)
            self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "lock"
        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert(cb_lock_span)

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "unlock"
        cb_unlock_span = get_first_span_by_filter(spans, filter)
        assert(cb_unlock_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_lock_span.t)
        self.assertEqual(test_span.t, cb_unlock_span.t)

        self.assertEqual(cb_lock_span.p, test_span.s)
        self.assertEqual(cb_unlock_span.p, test_span.s)

        assert(cb_lock_span.stack)
        self.assertIsNone(cb_lock_span.ec)
        assert(cb_unlock_span.stack)
        self.assertIsNone(cb_unlock_span.ec)

        self.assertEqual(cb_lock_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_lock_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_lock_span.data["couchbase"]["type"], 'lock')
        self.assertEqual(cb_unlock_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_unlock_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_unlock_span.data["couchbase"]["type"], 'unlock')

    def test_lock_unlock_muilti(self):
        res = None
        self.bucket.upsert("test_lock_unlock_multi_1", "lock_this")
        self.bucket.upsert("test_lock_unlock_multi_2", "lock_this")

        keys_to_lock = ("test_lock_unlock_multi_1", "test_lock_unlock_multi_2")

        with tracer.start_active_span('test'):
            rv = self.bucket.lock_multi(keys_to_lock, ttl=5)
            assert(rv)
            self.assertTrue(rv['test_lock_unlock_multi_1'].success)
            self.assertTrue(rv['test_lock_unlock_multi_2'].success)

            res = self.bucket.unlock_multi(rv)
            assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "lock_multi"
        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert(cb_lock_span)

        filter = lambda span: span.n == "couchbase" and span.data["couchbase"]["type"] == "unlock_multi"
        cb_unlock_span = get_first_span_by_filter(spans, filter)
        assert(cb_unlock_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_lock_span.t)
        self.assertEqual(test_span.t, cb_unlock_span.t)

        self.assertEqual(cb_lock_span.p, test_span.s)
        self.assertEqual(cb_unlock_span.p, test_span.s)

        assert(cb_lock_span.stack)
        self.assertIsNone(cb_lock_span.ec)
        assert(cb_unlock_span.stack)
        self.assertIsNone(cb_unlock_span.ec)

        self.assertEqual(cb_lock_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_lock_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_lock_span.data["couchbase"]["type"], 'lock_multi')
        self.assertEqual(cb_unlock_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_unlock_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_unlock_span.data["couchbase"]["type"], 'unlock_multi')

    def test_remove(self):
        res = None
        self.bucket.upsert("test_remove", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.remove("test_remove")

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'remove')

    def test_remove_multi(self):
        res = None
        self.bucket.upsert("test_remove_multi_1", 1)
        self.bucket.upsert("test_remove_multi_2", 1)

        keys_to_remove = ("test_remove_multi_1", "test_remove_multi_2")

        with tracer.start_active_span('test'):
            res = self.bucket.remove_multi(keys_to_remove)

        assert(res)
        self.assertTrue(res['test_remove_multi_1'].success)
        self.assertTrue(res['test_remove_multi_2'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'remove_multi')

    def test_counter(self):
        res = None
        self.bucket.upsert("test_counter", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.counter("test_counter", delta=10)

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'counter')

    def test_counter_multi(self):
        res = None
        self.bucket.upsert("first_test_counter", 1)
        self.bucket.upsert("second_test_counter", 1)

        with tracer.start_active_span('test'):
            res = self.bucket.counter_multi(("first_test_counter", "second_test_counter"))

        assert(res)
        self.assertTrue(res['first_test_counter'].success)
        self.assertTrue(res['second_test_counter'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'counter_multi')

    def test_mutate_in(self):
        res = None
        self.bucket.upsert('king_arthur', {'name': 'Arthur', 'email': 'kingarthur@couchbase.com',
                                    'interests': ['Holy Grail', 'African Swallows']})

        with tracer.start_active_span('test'):
            res = self.bucket.mutate_in('king_arthur',
                                    SD.array_addunique('interests', 'Cats'),
                                    SD.counter('updates', 1))

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'mutate_in')

    def test_lookup_in(self):
        res = None
        self.bucket.upsert('king_arthur', {'name': 'Arthur', 'email': 'kingarthur@couchbase.com',
                                    'interests': ['Holy Grail', 'African Swallows']})

        with tracer.start_active_span('test'):
            res = self.bucket.lookup_in('king_arthur',
                                        SD.get('email'),
                                        SD.get('interests'))

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'lookup_in')

    def test_stats(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.stats()

        assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'stats')

    def test_ping(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.ping()

        assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'ping')

    def test_diagnostics(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.diagnostics()

        assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'diagnostics')

    def test_observe(self):
        res = None
        self.bucket.upsert('test_observe', 1)

        with tracer.start_active_span('test'):
            res = self.bucket.observe('test_observe')

        assert(res)
        self.assertTrue(res.success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'observe')

    def test_observe_multi(self):
        res = None
        self.bucket.upsert('test_observe_multi_1', 1)
        self.bucket.upsert('test_observe_multi_2', 1)

        keys_to_observe = ('test_observe_multi_1', 'test_observe_multi_2')

        with tracer.start_active_span('test'):
            res = self.bucket.observe_multi(keys_to_observe)

        assert(res)
        self.assertTrue(res['test_observe_multi_1'].success)
        self.assertTrue(res['test_observe_multi_2'].success)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'observe_multi')

    def test_raw_n1ql_query(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.n1ql_query("SELECT 1")

        assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'n1ql_query')
        self.assertEqual(cb_span.data["couchbase"]["sql"], 'SELECT 1')

    def test_n1ql_query(self):
        res = None

        with tracer.start_active_span('test'):
            res = self.bucket.n1ql_query(N1QLQuery('SELECT name FROM `travel-sample` WHERE brewery_id ="mishawaka_brewing"'))

        assert(res)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        test_span = get_first_span_by_name(spans, 'sdk')
        assert(test_span)
        self.assertEqual(test_span.data["sdk"]["name"], 'test')

        cb_span = get_first_span_by_name(spans, 'couchbase')
        assert(cb_span)

        # Same traceId and parent relationship
        self.assertEqual(test_span.t, cb_span.t)
        self.assertEqual(cb_span.p, test_span.s)

        assert(cb_span.stack)
        self.assertIsNone(cb_span.ec)

        self.assertEqual(cb_span.data["couchbase"]["hostname"], "%s:8091" % testenv['couchdb_host'])
        self.assertEqual(cb_span.data["couchbase"]["bucket"], 'travel-sample')
        self.assertEqual(cb_span.data["couchbase"]["type"], 'n1ql_query')
        self.assertEqual(cb_span.data["couchbase"]["sql"], 'SELECT name FROM `travel-sample` WHERE brewery_id ="mishawaka_brewing"')
