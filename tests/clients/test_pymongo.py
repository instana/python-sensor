# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import json
import logging
from typing import Generator

import bson
import pymongo
import pytest

from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from tests.helpers import testenv

logger = logging.getLogger(__name__)


class TestPyMongoTracer:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.client = pymongo.MongoClient(
            host=testenv["mongodb_host"],
            port=int(testenv["mongodb_port"]),
            username=testenv["mongodb_user"],
            password=testenv["mongodb_pw"],
        )
        self.client.test.records.delete_many(filter={})
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        yield
        self.client.close()
        agent.options.allow_exit_as_root = False

    def test_successful_find_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.find_one({"type": "string"})
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "find"

        assert db_span.data["mongo"]["filter"] == '{"type": "string"}'
        assert not db_span.data["mongo"]["json"]

    def test_successful_find_query_as_root_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.client.test.records.find_one({"type": "string"})
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        db_span = spans[0]

        assert not db_span.p
        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "find"

        assert db_span.data["mongo"]["filter"] == '{"type": "string"}'
        assert not db_span.data["mongo"]["json"]

    def test_successful_insert_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.insert_one({"type": "string"})
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "insert"

        assert not db_span.data["mongo"]["filter"]

    def test_successful_update_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.update_one(
                {"type": "string"}, {"$set": {"type": "int"}}
            )
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "update"

        assert not db_span.data["mongo"]["filter"]
        assert db_span.data["mongo"]["json"]

        payload = json.loads(db_span.data["mongo"]["json"])
        assert {
            "q": {"type": "string"},
            "u": {"$set": {"type": "int"}},
            "multi": False,
            "upsert": False,
        } in payload

    def test_successful_delete_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.delete_one(filter={"type": "string"})
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "delete"

        assert not db_span.data["mongo"]["filter"]
        assert db_span.data["mongo"]["json"]

        payload = json.loads(db_span.data["mongo"]["json"])
        assert {"q": {"type": "string"}, "limit": 1} in payload

    def test_successful_aggregate_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.count_documents({"type": "string"})
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert db_span.data["mongo"]["command"] == "aggregate"

        assert not db_span.data["mongo"]["filter"]
        assert db_span.data["mongo"]["json"]

        payload = json.loads(db_span.data["mongo"]["json"])
        assert {"$match": {"type": "string"}} in payload

    @pytest.mark.skipif(
        pymongo.version_tuple >= (4, 0), reason="map reduce is removed in pymongo 4.0"
    )
    def test_successful_map_reduce_query(self) -> None:
        mapper = "function () { this.tags.forEach(function(z) { emit(z, 1); }); }"
        reducer = "function (key, values) { return len(values); }"

        with tracer.start_as_current_span("test"):
            self.client.test.records.map_reduce(
                bson.code.Code(mapper),
                bson.code.Code(reducer),
                "results",
                query={"x": {"$lt": 2}},
            )
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        test_span = spans[1]

        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mongo"
        assert (
            db_span.data["mongo"]["service"]
            == f"{testenv['mongodb_host']}:{testenv['mongodb_port']}"
        )
        assert db_span.data["mongo"]["namespace"] == "test.records"
        assert (
            db_span.data["mongo"]["command"].lower() == "mapreduce"
        )  # mapreduce command was renamed to mapReduce in pymongo 3.9.0

        assert db_span.data["mongo"]["filter"] == '{"x": {"$lt": 2}}'
        assert db_span.data["mongo"]["json"]

        payload = json.loads(db_span.data["mongo"]["json"])
        assert payload["map"], {"$code": mapper} == db_span.data["mongo"]["json"]
        assert payload["reduce"], {"$code": reducer} == db_span.data["mongo"]["json"]

    def test_successful_mutiple_queries(self) -> None:
        with tracer.start_as_current_span("test"):
            self.client.test.records.bulk_write(
                [
                    pymongo.InsertOne({"type": "string"}),
                    pymongo.UpdateOne({"type": "string"}, {"$set": {"type": "int"}}),
                    pymongo.DeleteOne({"type": "string"}),
                ]
            )
        current_span = get_current_span()
        assert not current_span.is_recording()

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        test_span = spans.pop()

        seen_span_ids = set()
        commands = []
        for span in spans:
            assert test_span.t == span.t
            assert span.p == test_span.s

            # check if all spans got a unique id
            assert span.s not in seen_span_ids

            seen_span_ids.add(span.s)
            commands.append(span.data["mongo"]["command"])

        # ensure spans are ordered the same way as commands
        assert commands == ["insert", "update", "delete"]
