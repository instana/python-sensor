from __future__ import absolute_import

import json
import unittest
import logging

from nose.tools import (assert_is_none, assert_is_not_none,
                        assert_false, assert_true, assert_list_equal)

from ..helpers import testenv
from instana.singletons import tracer

import pymongo
import bson

logger = logging.getLogger(__name__)


class TestPyMongo(unittest.TestCase):
    def setUp(self):
        self.conn = pymongo.MongoClient(host=testenv['mongodb_host'], port=int(testenv['mongodb_port']),
                                        username=testenv['mongodb_user'], password=testenv['mongodb_pw'])
        self.conn.test.records.delete_many(filter={})

        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        return None

    def test_successful_find_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.find_one({"type": "string"})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "find")

        self.assertEqual(db_span.data["mongo"]["filter"], '{"type": "string"}')
        assert_is_none(db_span.data["mongo"]["json"])

    def test_successful_insert_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.insert_one({"type": "string"})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "insert")

        assert_is_none(db_span.data["mongo"]["filter"])

    def test_successful_update_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.update_one({"type": "string"}, {"$set": {"type": "int"}})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "update")

        assert_is_none(db_span.data["mongo"]["filter"])
        assert_is_not_none(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        assert_true({
            "q": {"type": "string"},
            "u": {"$set": {"type": "int"}},
            "multi": False,
            "upsert": False
        } in payload, db_span.data["mongo"]["json"])

    def test_successful_delete_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.delete_one(filter={"type": "string"})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "delete")

        assert_is_none(db_span.data["mongo"]["filter"])
        assert_is_not_none(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        assert_true({"q": {"type": "string"}, "limit": 1} in payload, db_span.data["mongo"]["json"])

    def test_successful_aggregate_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.count_documents({"type": "string"})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "aggregate")

        assert_is_none(db_span.data["mongo"]["filter"])
        assert_is_not_none(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        assert_true({"$match": {"type": "string"}} in payload, db_span.data["mongo"]["json"])

    def test_successful_map_reduce_query(self):
        mapper = "function () { this.tags.forEach(function(z) { emit(z, 1); }); }"
        reducer = "function (key, values) { return len(values); }"

        with tracer.start_active_span("test"):
            self.conn.test.records.map_reduce(bson.code.Code(mapper), bson.code.Code(reducer), "results", query={"x": {"$lt": 2}})

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        assert_is_none(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"].lower(), "mapreduce") # mapreduce command was renamed to mapReduce in pymongo 3.9.0

        self.assertEqual(db_span.data["mongo"]["filter"], '{"x": {"$lt": 2}}')
        assert_is_not_none(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        self.assertEqual(payload["map"], {"$code": mapper}, db_span.data["mongo"]["json"])
        self.assertEqual(payload["reduce"], {"$code": reducer}, db_span.data["mongo"]["json"])

    def test_successful_mutiple_queries(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.bulk_write([pymongo.InsertOne({"type": "string"}),
                                               pymongo.UpdateOne({"type": "string"}, {"$set": {"type": "int"}}),
                                               pymongo.DeleteOne({"type": "string"})])

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 4)

        test_span = spans.pop()

        seen_span_ids = set()
        commands = []
        for span in spans:
            self.assertEqual(test_span.t, span.t)
            self.assertEqual(span.p, test_span.s)

            # check if all spans got a unique id
            assert_false(span.s in seen_span_ids)

            seen_span_ids.add(span.s)
            commands.append(span.data["mongo"]["command"])

        # ensure spans are ordered the same way as commands
        assert_list_equal(commands, ["insert", "update", "delete"])
