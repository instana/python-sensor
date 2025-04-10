# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
from typing import Generator

import boto3
import pytest
from moto import mock_aws

from instana.options import StandardOptions
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
        with tracer.start_as_current_span("test"):
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

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "CreateTable"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

    def test_ignore_dynamodb(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "dynamodb"
        agent.options = StandardOptions()

        with tracer.start_as_current_span("test"):
            self.dynamodb.create_table(
                TableName="dynamodb-table",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

        assert dynamodb_span not in filtered_spans

    def test_ignore_create_table(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "dynamodb:createtable"
        agent.options = StandardOptions()

        with tracer.start_as_current_span("test"):
            self.dynamodb.create_table(
                TableName="dynamodb-table",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
            )
            self.dynamodb.list_tables()

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 2

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(filtered_spans, filter)

        assert dynamodb_span.n == "dynamodb"
        assert dynamodb_span.data["dynamodb"]["op"] == "ListTables"

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
        dynamodb_span = spans[0]
        assert dynamodb_span
        assert dynamodb_span.n == "dynamodb"
        assert not dynamodb_span.p
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "CreateTable"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

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

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "ListTables"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"

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

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "PutItem"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

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

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "Scan"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

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

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "GetItem"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

    def test_dynamodb_update_item(self) -> None:
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
            self.dynamodb.update_item(
                TableName="dynamodb-table",
                Key={"id": {"S": "1"}},  # Specify the key
                UpdateExpression="SET #attr_name = :new_name",
                ExpressionAttributeNames={"#attr_name": "name"},  # Use alias for "name"
                ExpressionAttributeValues={":new_name": {"S": "Updated John"}},
                ReturnValues="UPDATED_NEW",
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "UpdateItem"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

    def test_dynamodb_delete_item(self) -> None:
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
            self.dynamodb.delete_item(
                TableName="dynamodb-table", Key={"id": {"S": "1"}}
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "DeleteItem"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"

    def test_dynamodb_query_item(self) -> None:
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
        self.dynamodb.put_item(
            TableName="dynamodb-table", Item={"id": {"S": "2"}, "name": {"S": "Jack"}}
        )
        with tracer.start_as_current_span("test"):
            self.dynamodb.query(
                TableName="dynamodb-table",
                KeyConditionExpression="id = :pk_val",
                ExpressionAttributeValues={":pk_val": {"S": "1"}},
            )

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "dynamodb"  # noqa: E731
        dynamodb_span = get_first_span_by_filter(spans, filter)
        assert dynamodb_span

        assert dynamodb_span.t == test_span.t
        assert dynamodb_span.p == test_span.s

        assert not test_span.ec
        assert not dynamodb_span.ec

        assert dynamodb_span.data["dynamodb"]["op"] == "Query"
        assert dynamodb_span.data["dynamodb"]["region"] == "us-west-2"
        assert dynamodb_span.data["dynamodb"]["table"] == "dynamodb-table"
