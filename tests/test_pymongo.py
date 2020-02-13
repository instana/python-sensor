from __future__ import absolute_import

import logging

from nose.tools import (assert_equals, assert_not_equals, assert_is_none, assert_is_not_none,
                        assert_false, assert_true, assert_is_instance, assert_greater, assert_list_equal)

from .helpers import testenv
from instana.singletons import tracer
from instana.util import to_json

import pymongo
import bson

logger = logging.getLogger(__name__)

class TestPyMongo:
    def setUp(self):
        logger.warn("Connecting to MongoDB mongo://%s:<pass>@%s:%s",
                    testenv['mongodb_user'], testenv['mongodb_host'], testenv['mongodb_port'])

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
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "find")
        assert_equals(db_span.data.mongo.filter, {"type": "string"})
        assert_is_none(db_span.data.mongo.json)

    def test_successful_insert_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.insert_one({"type": "string"})
        
        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "insert")
        assert_is_none(db_span.data.mongo.filter)

    def test_successful_update_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.update_one({"type": "string"}, {"$set": {"type": "int"}})
        
        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "update")
        assert_is_none(db_span.data.mongo.filter)
        assert_equals(db_span.data.mongo.json, [{"q": {"type": "string"}, "u": {"$set": {"type": "int"}}, "multi": False, "upsert": False}])

    def test_successful_delete_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.delete_one(filter={"type": "string"})
        
        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "delete")
        assert_is_none(db_span.data.mongo.filter)
        assert_equals(db_span.data.mongo.json, [{"q": {"type": "string"}, "limit": 1}])

    def test_successful_aggregate_query(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.count_documents({"type": "string"})
        
        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "aggregate")
        assert_is_none(db_span.data.mongo.filter)
        assert_equals(db_span.data.mongo.json, [{'$match': {'type': 'string'}}, {'$group': {'_id': None, 'n': {'$sum': 1}}}])

    def test_successful_map_reduce_query(self):
        mapper = bson.code.Code("function () { this.tags.forEach(function(z) { emit(z, 1); }); }")
        reducer = bson.code.Code("function (key, values) { return len(values); }")
        
        with tracer.start_active_span("test"):
            self.conn.test.records.map_reduce(mapper, reducer, "results", query={"x": {"$lt": 2}})
        
        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 2)

        db_span = spans[0]
        test_span = spans[1]

        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)
        
        assert_false(db_span.error)
        assert_is_none(db_span.ec)

        assert_equals(db_span.n, "mongo")
        assert_equals(db_span.data.mongo.service, "%s:%s" % (testenv['mongodb_host'], testenv['mongodb_port']))
        assert_equals(db_span.data.mongo.namespace, "test.records")
        assert_equals(db_span.data.mongo.command, "mapreduce")
        assert_equals(db_span.data.mongo.json, {"map": mapper, "reduce": reducer, "query": {"x": {"$lt": 2}}})

    def test_successful_mutiple_queries(self):
        with tracer.start_active_span("test"):
            self.conn.test.records.bulk_write([pymongo.InsertOne({"type": "string"}),
                                               pymongo.UpdateOne({"type": "string"}, {"$set": {"type": "int"}}),
                                               pymongo.DeleteOne({"type": "string"})])

        assert_is_none(tracer.active_span)

        spans = self.recorder.queued_spans()
        assert_equals(len(spans), 4)

        test_span = spans.pop()
        
        seen_span_ids = set()
        commands = []
        for span in spans:
            assert_equals(test_span.t, span.t)
            assert_equals(span.p, test_span.s)

            # check if all spans got a unique id
            assert_false(span.s in seen_span_ids)
            
            seen_span_ids.add(span.s)
            commands.append(span.data.mongo.command)

        # ensure spans are ordered the same way as commands
        assert_list_equal(commands, ["insert", "update", "delete"])
