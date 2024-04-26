# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import json
import unittest
import logging

from ..helpers import testenv
from instana.singletons import agent, tracer

import pymongo
import bson

logger = logging.getLogger(__name__)

pymongoversion = unittest.skipIf(
    pymongo.version_tuple >= (4, 0), reason="map reduce is removed in pymongo 4.0"
)


class TestPyMongoTracer(unittest.TestCase):
    def setUp(self):
        self.client = pymongo.MongoClient(host=testenv['mongodb_host'], port=int(testenv['mongodb_port']),
                                          username=testenv['mongodb_user'], password=testenv['mongodb_pw'])
        self.client.test.records.delete_many(filter={})

        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        self.client.close()
        agent.options.allow_exit_as_root = False

    def test_successful_find_query(self):
        with tracer.start_active_span("test"):
            self.client.test.records.find_one({"type": "string"})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "find")

        self.assertEqual(db_span.data["mongo"]["filter"], '{"type": "string"}')
        self.assertIsNone(db_span.data["mongo"]["json"])

    def test_successful_find_query_as_root_span(self):
        agent.options.allow_exit_as_root = True
        self.client.test.records.find_one({"type": "string"})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 1)

        db_span = spans[0]

        self.assertEqual(db_span.p, None)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "find")

        self.assertEqual(db_span.data["mongo"]["filter"], '{"type": "string"}')
        self.assertIsNone(db_span.data["mongo"]["json"])

    def test_successful_insert_query(self):
        with tracer.start_active_span("test"):
            self.client.test.records.insert_one({"type": "string"})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "insert")

        self.assertIsNone(db_span.data["mongo"]["filter"])

    def test_successful_update_query(self):
        with tracer.start_active_span("test"):
            self.client.test.records.update_one({"type": "string"}, {"$set": {"type": "int"}})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "update")

        self.assertIsNone(db_span.data["mongo"]["filter"])
        self.assertIsNotNone(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        self.assertIn({
                        "q": {"type": "string"},
                        "u": {"$set": {"type": "int"}},
                        "multi": False,
                        "upsert": False
                       }, payload)

    def test_successful_delete_query(self):
        with tracer.start_active_span("test"):
            self.client.test.records.delete_one(filter={"type": "string"})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "delete")

        self.assertIsNone(db_span.data["mongo"]["filter"])
        self.assertIsNotNone(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        self.assertIn({"q": {"type": "string"}, "limit": 1}, payload)

    def test_successful_aggregate_query(self):
        with tracer.start_active_span("test"):
            self.client.test.records.count_documents({"type": "string"})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"], "aggregate")

        self.assertIsNone(db_span.data["mongo"]["filter"])
        self.assertIsNotNone(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        self.assertIn({"$match": {"type": "string"}}, payload)

    @pymongoversion
    def test_successful_map_reduce_query(self):
        mapper = "function () { this.tags.forEach(function(z) { emit(z, 1); }); }"
        reducer = "function (key, values) { return len(values); }"

        with tracer.start_active_span("test"):
            self.client.test.records.map_reduce(bson.code.Code(mapper), bson.code.Code(reducer), "results",
                                              query={"x": {"$lt": 2}})

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mongo")
        self.assertEqual(db_span.data["mongo"]["service"], "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        self.assertEqual(db_span.data["mongo"]["namespace"], "test.records")
        self.assertEqual(db_span.data["mongo"]["command"].lower(),
                         "mapreduce")  # mapreduce command was renamed to mapReduce in pymongo 3.9.0

        self.assertEqual(db_span.data["mongo"]["filter"], '{"x": {"$lt": 2}}')
        self.assertIsNotNone(db_span.data["mongo"]["json"])

        payload = json.loads(db_span.data["mongo"]["json"])
        self.assertEqual(payload["map"], {"$code": mapper}, db_span.data["mongo"]["json"])
        self.assertEqual(payload["reduce"], {"$code": reducer}, db_span.data["mongo"]["json"])

    def test_successful_mutiple_queries(self):
        with tracer.start_active_span("test"):
            self.client.test.records.bulk_write([pymongo.InsertOne({"type": "string"}),
                                                 pymongo.UpdateOne({"type": "string"}, {"$set": {"type": "int"}}),
                                                 pymongo.DeleteOne({"type": "string"})])

        self.assertIsNone(tracer.active_span)

        spans = self.recorder.queued_spans()
        self.assertEqual(len(spans), 4)

        test_span = spans.pop()

        seen_span_ids = set()
        commands = []
        for span in spans:
            self.assertEqual(test_span.t, span.t)
            self.assertEqual(span.p, test_span.s)

            # check if all spans got a unique id
            self.assertNotIn(span.s, seen_span_ids)

            seen_span_ids.add(span.s)
            commands.append(span.data["mongo"]["command"])

        # ensure spans are ordered the same way as commands
        self.assertListEqual(commands, ["insert", "update", "delete"])

