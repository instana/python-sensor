# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import time
from typing import Generator
from unittest.mock import patch

import pytest

from instana.singletons import agent, tracer
from tests.helpers import testenv, get_first_span_by_name, get_first_span_by_filter

from couchbase.admin import Admin
from couchbase.cluster import Cluster
from couchbase.bucket import Bucket
from couchbase.exceptions import (
    CouchbaseTransientError,
    HTTPError,
    KeyExistsError,
    NotFoundError,
)
import couchbase.subdocument as SD
from couchbase.n1ql import N1QLQuery

# Delete any pre-existing buckets.  Create new.
cb_adm = Admin(
    testenv["couchdb_username"],
    testenv["couchdb_password"],
    host=testenv["couchdb_host"],
    port=8091,
)

# Make sure a test bucket exists
try:
    cb_adm.bucket_create("travel-sample")
    cb_adm.wait_ready("travel-sample", timeout=30)
except HTTPError:
    pass


class TestStandardCouchDB:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.cluster = Cluster("couchbase://%s" % testenv["couchdb_host"])
        self.bucket = Bucket(
            "couchbase://%s/travel-sample" % testenv["couchdb_host"],
            username=testenv["couchdb_username"],
            password=testenv["couchdb_password"],
        )
        self.bucket.upsert("test-key", 1)
        time.sleep(0.5)
        self.recorder.clear_spans()
        yield
        agent.options.allow_exit_as_root = False

    def test_vanilla_get(self) -> None:
        res = self.bucket.get("test-key")
        assert res

    def test_upsert(self) -> None:
        res = None
        with tracer.start_as_current_span("test"):
            res = self.bucket.upsert("test_upsert", 1)

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "upsert"

    def test_upsert_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        res = self.bucket.upsert("test_upsert", 1)

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        assert not cb_span.p

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "upsert"

    def test_upsert_multi(self) -> None:
        res = None

        kvs = {}
        kvs["first_test_upsert_multi"] = 1
        kvs["second_test_upsert_multi"] = 1

        with tracer.start_as_current_span("test"):
            res = self.bucket.upsert_multi(kvs)

        assert res
        assert res["first_test_upsert_multi"].success
        assert res["second_test_upsert_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "upsert_multi"

    def test_insert_new(self) -> None:
        res = None
        try:
            self.bucket.remove("test_insert_new")
        except NotFoundError:
            pass

        with tracer.start_as_current_span("test"):
            res = self.bucket.insert("test_insert_new", 1)

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "insert"

    def test_insert_existing(self) -> None:
        res = None
        try:
            self.bucket.insert("test_insert", 1)
        except KeyExistsError:
            pass

        try:
            with tracer.start_as_current_span("test"):
                res = self.bucket.insert("test_insert", 1)
        except KeyExistsError:
            pass

        assert not res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert cb_span.ec == 1
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("_KeyExistsError")
        assert not found == -1

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "insert"

    def test_insert_multi(self) -> None:
        res = None

        kvs = {}
        kvs["first_test_upsert_multi"] = 1
        kvs["second_test_upsert_multi"] = 1

        try:
            self.bucket.remove("first_test_upsert_multi")
            self.bucket.remove("second_test_upsert_multi")
        except NotFoundError:
            pass

        with tracer.start_as_current_span("test"):
            res = self.bucket.insert_multi(kvs)

        assert res
        assert res["first_test_upsert_multi"].success
        assert res["second_test_upsert_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "insert_multi"

    def test_replace(self) -> None:
        res = None
        try:
            self.bucket.insert("test_replace", 1)
        except KeyExistsError:
            pass

        with tracer.start_as_current_span("test"):
            res = self.bucket.replace("test_replace", 2)

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "replace"

    def test_replace_non_existent(self) -> None:
        res = None

        try:
            self.bucket.remove("test_replace")
        except NotFoundError:
            pass

        try:
            with tracer.start_as_current_span("test"):
                res = self.bucket.replace("test_replace", 2)
        except NotFoundError:
            pass

        assert not res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert cb_span.ec == 1
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("NotFoundError")
        assert not found == -1

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "replace"

    def test_replace_multi(self) -> None:
        res = None

        kvs = {}
        kvs["first_test_replace_multi"] = 1
        kvs["second_test_replace_multi"] = 1

        self.bucket.upsert("first_test_replace_multi", "one")
        self.bucket.upsert("second_test_replace_multi", "two")

        with tracer.start_as_current_span("test"):
            res = self.bucket.replace_multi(kvs)

        assert res
        assert res["first_test_replace_multi"].success
        assert res["second_test_replace_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "replace_multi"

    def test_append(self) -> None:
        self.bucket.upsert("test_append", "one")

        res = None
        with tracer.start_as_current_span("test"):
            res = self.bucket.append("test_append", "two")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "append"

    def test_append_multi(self) -> None:
        res = None

        kvs = dict()
        kvs["first_test_append_multi"] = "ok1"
        kvs["second_test_append_multi"] = "ok2"

        self.bucket.upsert("first_test_append_multi", "one")
        self.bucket.upsert("second_test_append_multi", "two")

        with tracer.start_as_current_span("test"):
            res = self.bucket.append_multi(kvs)

        assert res
        assert res["first_test_append_multi"].success
        assert res["second_test_append_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "append_multi"

    def test_prepend(self) -> None:
        self.bucket.upsert("test_prepend", "one")

        res = None
        with tracer.start_as_current_span("test"):
            res = self.bucket.prepend("test_prepend", "two")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "prepend"

    def test_prepend_multi(self) -> None:
        res = None

        kvs = {}
        kvs["first_test_prepend_multi"] = "ok1"
        kvs["second_test_prepend_multi"] = "ok2"

        self.bucket.upsert("first_test_prepend_multi", "one")
        self.bucket.upsert("second_test_prepend_multi", "two")

        with tracer.start_as_current_span("test"):
            res = self.bucket.prepend_multi(kvs)

        assert res
        assert res["first_test_prepend_multi"].success
        assert res["second_test_prepend_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "prepend_multi"

    def test_get(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.get("test-key")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "get"

    def test_rget(self) -> None:
        res = None

        try:
            with tracer.start_as_current_span("test"):
                res = self.bucket.rget("test-key", replica_index=None)
        except CouchbaseTransientError:
            pass

        assert not res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert cb_span.ec == 1
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("CouchbaseTransientError")
        assert found != -1

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "rget"

    def test_get_not_found(self) -> None:
        res = None
        try:
            self.bucket.remove("test_get_not_found")
        except NotFoundError:
            pass

        try:
            with tracer.start_as_current_span("test"):
                res = self.bucket.get("test_get_not_found")
        except NotFoundError:
            pass

        assert not res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert cb_span.ec == 1
        # Just search for the substring of the exception class
        found = cb_span.data["couchbase"]["error"].find("NotFoundError")
        assert found != -1

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "get"

    def test_get_multi(self) -> None:
        res = None

        self.bucket.upsert("first_test_get_multi", "one")
        self.bucket.upsert("second_test_get_multi", "two")

        with tracer.start_as_current_span("test"):
            res = self.bucket.get_multi(
                ["first_test_get_multi", "second_test_get_multi"]
            )

        assert res
        assert res["first_test_get_multi"].success
        assert res["second_test_get_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "get_multi"

    def test_touch(self) -> None:
        res = None
        self.bucket.upsert("test_touch", 1)

        with tracer.start_as_current_span("test"):
            res = self.bucket.touch("test_touch")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "touch"

    def test_touch_multi(self) -> None:
        res = None

        self.bucket.upsert("first_test_touch_multi", "one")
        self.bucket.upsert("second_test_touch_multi", "two")

        with tracer.start_as_current_span("test"):
            res = self.bucket.touch_multi(
                ["first_test_touch_multi", "second_test_touch_multi"]
            )

        assert res
        assert res["first_test_touch_multi"].success
        assert res["second_test_touch_multi"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "touch_multi"

    def test_lock(self) -> None:
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_as_current_span("test"):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            assert rv
            assert rv.success

            # upsert automatically unlocks the key
            res = self.bucket.upsert("test_lock_unlock", "updated", rv.cas)
            assert res
            assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        def filter(span):
            return span.n == "couchbase" and span.data["couchbase"]["type"] == "lock"

        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert cb_lock_span

        def filter(span):
            return span.n == "couchbase" and span.data["couchbase"]["type"] == "upsert"

        cb_upsert_span = get_first_span_by_filter(spans, filter)
        assert cb_upsert_span

        # Same traceId and parent relationship
        assert cb_lock_span.t == test_span.t
        assert cb_upsert_span.t == test_span.t

        assert cb_lock_span.p == test_span.s
        assert cb_upsert_span.p == test_span.s

        assert cb_lock_span.stack
        assert not cb_lock_span.ec
        assert cb_upsert_span.stack
        assert not cb_upsert_span.ec

        assert (
            cb_lock_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_lock_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_lock_span.data["couchbase"]["type"] == "lock"
        assert (
            cb_upsert_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_upsert_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_upsert_span.data["couchbase"]["type"] == "upsert"

    def test_lock_unlock(self) -> None:
        res = None
        self.bucket.upsert("test_lock_unlock", "lock_this")

        with tracer.start_as_current_span("test"):
            rv = self.bucket.lock("test_lock_unlock", ttl=5)
            assert rv
            assert rv.success

            # upsert automatically unlocks the key
            res = self.bucket.unlock("test_lock_unlock", rv.cas)
            assert res
            assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        def filter(span):
            return span.n == "couchbase" and span.data["couchbase"]["type"] == "lock"

        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert cb_lock_span

        def filter(span):
            return span.n == "couchbase" and span.data["couchbase"]["type"] == "unlock"

        cb_unlock_span = get_first_span_by_filter(spans, filter)
        assert cb_unlock_span

        # Same traceId and parent relationship
        assert cb_lock_span.t == test_span.t
        assert cb_unlock_span.t == test_span.t

        assert cb_lock_span.p == test_span.s
        assert cb_unlock_span.p == test_span.s

        assert cb_lock_span.stack
        assert not cb_lock_span.ec
        assert cb_unlock_span.stack
        assert not cb_unlock_span.ec

        assert (
            cb_lock_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_lock_span.data["couchbase"]["bucket"], "travel-sample"
        assert cb_lock_span.data["couchbase"]["type"], "lock"
        assert (
            cb_unlock_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_unlock_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_unlock_span.data["couchbase"]["type"] == "unlock"

    def test_lock_unlock_muilti(self) -> None:
        res = None
        self.bucket.upsert("test_lock_unlock_multi_1", "lock_this")
        self.bucket.upsert("test_lock_unlock_multi_2", "lock_this")

        keys_to_lock = ("test_lock_unlock_multi_1", "test_lock_unlock_multi_2")

        with tracer.start_as_current_span("test"):
            rv = self.bucket.lock_multi(keys_to_lock, ttl=5)
            assert rv
            assert rv["test_lock_unlock_multi_1"].success
            assert rv["test_lock_unlock_multi_2"].success

            res = self.bucket.unlock_multi(rv)
            assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        def filter(span):
            return (
                span.n == "couchbase" and span.data["couchbase"]["type"] == "lock_multi"
            )

        cb_lock_span = get_first_span_by_filter(spans, filter)
        assert cb_lock_span

        def filter(span):
            return (
                span.n == "couchbase"
                and span.data["couchbase"]["type"] == "unlock_multi"
            )

        cb_unlock_span = get_first_span_by_filter(spans, filter)
        assert cb_unlock_span

        # Same traceId and parent relationship
        assert cb_lock_span.t == test_span.t
        assert cb_unlock_span.t == test_span.t

        assert cb_lock_span.p == test_span.s
        assert cb_unlock_span.p == test_span.s

        assert cb_lock_span.stack
        assert not cb_lock_span.ec
        assert cb_unlock_span.stack
        assert not cb_unlock_span.ec

        assert (
            cb_lock_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_lock_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_lock_span.data["couchbase"]["type"] == "lock_multi"
        assert (
            cb_unlock_span.data["couchbase"]["hostname"]
            == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_unlock_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_unlock_span.data["couchbase"]["type"] == "unlock_multi"

    def test_remove(self) -> None:
        res = None
        self.bucket.upsert("test_remove", 1)

        with tracer.start_as_current_span("test"):
            res = self.bucket.remove("test_remove")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "remove"

    def test_remove_multi(self) -> None:
        res = None
        self.bucket.upsert("test_remove_multi_1", 1)
        self.bucket.upsert("test_remove_multi_2", 1)

        keys_to_remove = ("test_remove_multi_1", "test_remove_multi_2")

        with tracer.start_as_current_span("test"):
            res = self.bucket.remove_multi(keys_to_remove)

        assert res
        assert res["test_remove_multi_1"].success
        assert res["test_remove_multi_2"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "remove_multi"

    def test_counter(self) -> None:
        res = None
        self.bucket.upsert("test_counter", 1)

        with tracer.start_as_current_span("test"):
            res = self.bucket.counter("test_counter", delta=10)

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "counter"

    def test_counter_multi(self) -> None:
        res = None
        self.bucket.upsert("first_test_counter", 1)
        self.bucket.upsert("second_test_counter", 1)

        with tracer.start_as_current_span("test"):
            res = self.bucket.counter_multi(
                ("first_test_counter", "second_test_counter")
            )

        assert res
        assert res["first_test_counter"].success
        assert res["second_test_counter"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "counter_multi"

    def test_mutate_in(self) -> None:
        res = None
        self.bucket.upsert(
            "king_arthur",
            {
                "name": "Arthur",
                "email": "kingarthur@couchbase.com",
                "interests": ["Holy Grail", "African Swallows"],
            },
        )

        with tracer.start_as_current_span("test"):
            res = self.bucket.mutate_in(
                "king_arthur",
                SD.array_addunique("interests", "Cats"),
                SD.counter("updates", 1),
            )

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "mutate_in"

    def test_lookup_in(self) -> None:
        res = None
        self.bucket.upsert(
            "king_arthur",
            {
                "name": "Arthur",
                "email": "kingarthur@couchbase.com",
                "interests": ["Holy Grail", "African Swallows"],
            },
        )

        with tracer.start_as_current_span("test"):
            res = self.bucket.lookup_in(
                "king_arthur", SD.get("email"), SD.get("interests")
            )

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "lookup_in"

    def test_stats(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.stats()

        assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "stats"

    def test_ping(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.ping()

        assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "ping"

    def test_diagnostics(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.diagnostics()

        assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "diagnostics"

    def test_observe(self) -> None:
        res = None
        self.bucket.upsert("test_observe", 1)

        with tracer.start_as_current_span("test"):
            res = self.bucket.observe("test_observe")

        assert res
        assert res.success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "observe"

    def test_observe_multi(self) -> None:
        res = None
        self.bucket.upsert("test_observe_multi_1", 1)
        self.bucket.upsert("test_observe_multi_2", 1)

        keys_to_observe = ("test_observe_multi_1", "test_observe_multi_2")

        with tracer.start_as_current_span("test"):
            res = self.bucket.observe_multi(keys_to_observe)

        assert res
        assert res["test_observe_multi_1"].success
        assert res["test_observe_multi_2"].success

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "observe_multi"

    def test_query_with_instana_tracing_off(self) -> None:
        res = None

        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.couchbase_inst.tracing_is_off", return_value=True
        ):
            res = self.bucket.n1ql_query("SELECT 1")
        assert res

    def test_query_with_instana_exception(self) -> None:
        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.couchbase_inst.collect_attributes",
            side_effect=Exception("test-error"),
        ):
            self.bucket.n1ql_query("SELECT 1")

        spans = self.recorder.queued_spans()
        cb_span = get_first_span_by_name(spans, "couchbase")

        assert cb_span.data["couchbase"]["error"] == "Exception('test-error')"

    def test_raw_n1ql_query(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.n1ql_query("SELECT 1")

        assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "n1ql_query"
        assert cb_span.data["couchbase"]["sql"] == "SELECT 1"

    def test_n1ql_query(self) -> None:
        res = None

        with tracer.start_as_current_span("test"):
            res = self.bucket.n1ql_query(
                N1QLQuery(
                    'SELECT name FROM `travel-sample` WHERE brewery_id ="mishawaka_brewing"'
                )
            )

        assert res

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        test_span = get_first_span_by_name(spans, "sdk")
        assert test_span
        assert test_span.data["sdk"]["name"] == "test"

        cb_span = get_first_span_by_name(spans, "couchbase")
        assert cb_span

        # Same traceId and parent relationship
        assert cb_span.t == test_span.t
        assert cb_span.p == test_span.s

        assert cb_span.stack
        assert not cb_span.ec

        assert (
            cb_span.data["couchbase"]["hostname"] == f"{testenv['couchdb_host']}:8091"
        )
        assert cb_span.data["couchbase"]["bucket"] == "travel-sample"
        assert cb_span.data["couchbase"]["type"] == "n1ql_query"
        assert (
            cb_span.data["couchbase"]["sql"]
            == 'SELECT name FROM `travel-sample` WHERE brewery_id ="mishawaka_brewing"'
        )
