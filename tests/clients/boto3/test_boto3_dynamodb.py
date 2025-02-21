# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import Generator

import boto3
import pytest
from moto import mock_aws

from instana.singletons import agent, tracer
from tests.helpers import get_first_span_by_filter


class TestDynamoDB:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.dynamodb = boto3.client("dynamodb", region_name="us-west-2")
        yield
        self.mock.stop()
        agent.options.allow_exit_as_root = False

    def test_vanilla_create_table(self) -> None:
        self.dynamodb.create_table(
            TableName="dynamodb-table",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        result = self.dynamodb.list_tables()
        assert len(result["TableNames"]) == 1
        assert result["TableNames"][0] == "dynamodb-table"

    def test_dynamodb_create_table(self) -> None:
        with tracer.start_as_current_span("dynamodb"):
            self.dynamodb.create_table(
                TableName="dynamodb-table",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            )
        result = self.dynamodb.list_tables()
        assert len(result["TableNames"]) == 1
        assert result["TableNames"][0] == "dynamodb-table"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "CreateTable"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        }
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/CreateTable"
        )

    def test_dynamodb_create_table_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.dynamodb.create_table(
            TableName="dynamodb-table",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        agent.options.allow_exit_as_root = False
        result = self.dynamodb.list_tables()
        assert len(result["TableNames"]) == 1
        assert result["TableNames"][0] == "dynamodb-table"

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        boto_span = spans[0]
        assert boto_span
        assert boto_span.n == "boto3"
        assert not boto_span.p
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "CreateTable"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        }
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/CreateTable"
        )

    def test_dynamodb_list_tables(self) -> None:
        with tracer.start_as_current_span("test"):
            result = self.dynamodb.list_tables()

        assert len(result["TableNames"]) == 0
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "ListTables"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {}
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/ListTables"
        )

    def test_dynamodb_put_item(self) -> None:
        self.dynamodb.create_table(
            TableName="dynamodb-table",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        with tracer.start_as_current_span("test"):
            self.dynamodb.put_item(
                TableName="dynamodb-table",
                Item={"id": {"S": "1"}, "name": {"S": "John"}},
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "PutItem"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "Item": {"id": {"S": "1"}, "name": {"S": "John"}},
        }
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/PutItem"
        )
        assert boto_span.data["http"]["status"] == 200

    def test_dynamodb_scan(self) -> None:
        test_item = {"id": {"S": "1"}, "name": {"S": "John"}}
        self.dynamodb.create_table(
            TableName="dynamodb-table",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        self.dynamodb.put_item(
            TableName="dynamodb-table",
            Item=test_item,
        )
        with tracer.start_as_current_span("test"):
            result = self.dynamodb.scan(TableName="dynamodb-table")

        assert result["Items"] == [test_item]
        assert result["Count"] == 1
        assert result["ScannedCount"] == 1
        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "Scan"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {"TableName": "dynamodb-table"}
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/Scan"
        )
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["status"] == 200

    def test_dynamodb_get_item(self) -> None:
        test_item = {"id": {"S": "1"}, "name": {"S": "John"}}
        self.dynamodb.create_table(
            TableName="dynamodb-table",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        )
        self.dynamodb.put_item(
            TableName="dynamodb-table",
            Item=test_item,
        )
        with tracer.start_as_current_span("test"):
            result = self.dynamodb.get_item(
                TableName="dynamodb-table", Key={"id": {"S": "1"}}
            )

        assert result["Item"] == test_item
        assert result["ResponseMetadata"]

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "GetItem"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "Key": {"id": {"S": "1"}},
        }
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/GetItem"
        )
        assert boto_span.data["http"]["method"] == "POST"
        assert boto_span.data["http"]["status"] == 200

    def test_request_header_capture_before_call(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This", "X-Capture-That"]

        event_system = self.dynamodb.meta.events

        request_headers = {"X-Capture-This": "this", "X-Capture-That": "that"}

        def add_custom_header_before_call(params, **kwargs):
            params["headers"].update(request_headers)

        event_system.register(
            "before-call.dynamodb.CreateTable",
            add_custom_header_before_call,
        )

        with tracer.start_as_current_span("test"):
            self.dynamodb.create_table(
                TableName="dynamodb-table",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            )

        result = self.dynamodb.list_tables()

        assert len(result["TableNames"]) == 1
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "CreateTable"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        }
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/CreateTable"
        )

        assert boto_span.data["http"]["header"]["X-Capture-This"] == "this"
        assert boto_span.data["http"]["header"]["X-Capture-That"] == "that"

        agent.options.extra_http_headers = original_extra_http_headers

    def test_response_header_capture(self) -> None:
        original_extra_http_headers = agent.options.extra_http_headers
        agent.options.extra_http_headers = ["X-Capture-This-Too", "X-Capture-That-Too"]

        event_system = self.dynamodb.meta.events

        response_headers = {
            "X-Capture-This-Too": "this too",
            "X-Capture-That-Too": "that too",
        }

        def modify_after_call_args(parsed, **kwargs):
            parsed["ResponseMetadata"]["HTTPHeaders"].update(response_headers)

        event_system.register(
            "after-call.dynamodb.CreateTable",
            modify_after_call_args,
        )

        with tracer.start_as_current_span("test"):
            self.dynamodb.create_table(
                TableName="dynamodb-table",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            )

        result = self.dynamodb.list_tables()

        assert len(result["TableNames"]) == 1
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "boto3"  # noqa: E731
        boto_span = get_first_span_by_filter(spans, filter)
        assert boto_span

        assert boto_span.t == test_span.t
        assert boto_span.p == test_span.s

        assert not test_span.ec
        assert not boto_span.ec

        assert boto_span.data["boto3"]["op"] == "CreateTable"
        assert (
            boto_span.data["boto3"]["ep"] == "https://dynamodb.us-west-2.amazonaws.com"
        )
        assert boto_span.data["boto3"]["reg"] == "us-west-2"
        assert boto_span.data["boto3"]["payload"] == {
            "TableName": "dynamodb-table",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
            "ProvisionedThroughput": {"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
        }
        assert boto_span.data["http"]["status"] == 200
        assert boto_span.data["http"]["method"] == "POST"
        assert (
            boto_span.data["http"]["url"]
            == "https://dynamodb.us-west-2.amazonaws.com:443/CreateTable"
        )

        assert boto_span.data["http"]["header"]["X-Capture-This-Too"] == "this too"
        assert boto_span.data["http"]["header"]["X-Capture-That-Too"] == "that too"

        agent.options.extra_http_headers = original_extra_http_headers
