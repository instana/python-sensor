# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import pytest
from typing import Generator
from moto import mock_aws
import boto3

from instana.singletons import tracer, agent
from tests.helpers import get_first_span_by_filter

pwd = os.path.dirname(os.path.abspath(__file__))
upload_filename = os.path.abspath(pwd + "/../../data/boto3/test_upload_file.jpg")
download_target_filename = os.path.abspath(
    pwd + "/../../data/boto3/download_target_file.asdf"
)


class TestS3:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and Teardown"""
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.mock = mock_aws()
        self.mock.start()
        self.s3 = boto3.client("s3", region_name="us-east-1")
        yield
        # Stop Moto after each test
        self.mock.stop()
        agent.options.allow_exit_as_root = False

    def test_vanilla_create_bucket(self) -> None:
        self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        assert len(result["Buckets"]) == 1
        assert result["Buckets"][0]["Name"] == "aws_bucket_name"

    def test_s3_create_bucket(self) -> None:
        with tracer.start_as_current_span("test"):
            self.s3.create_bucket(Bucket="aws_bucket_name")

        result = self.s3.list_buckets()
        assert len(result["Buckets"]) == 1
        assert result["Buckets"][0]["Name"] == "aws_bucket_name"

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "CreateBucket"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_create_bucket_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.s3.create_bucket(Bucket="aws_bucket_name")

        agent.options.allow_exit_as_root = False
        self.s3.list_buckets()

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        s3_span = spans[0]
        assert s3_span

        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "CreateBucket"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_list_buckets(self) -> None:
        with tracer.start_as_current_span("test"):
            result = self.s3.list_buckets()

        assert len(result["Buckets"]) == 0
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "ListBuckets"
        assert not s3_span.data["s3"]["bucket"]

    def test_s3_vanilla_upload_file(self) -> None:
        object_name = "aws_key_name"
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)
        result = self.s3.upload_file(upload_filename, bucket_name, object_name)
        assert not result

    def test_s3_upload_file(self) -> None:
        object_name = "aws_key_name"
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)

        with tracer.start_as_current_span("test"):
            self.s3.upload_file(upload_filename, bucket_name, object_name)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "UploadFile"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_upload_file_obj(self) -> None:
        object_name = "aws_key_name"
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)

        with tracer.start_as_current_span("test"):
            with open(upload_filename, "rb") as fd:
                self.s3.upload_fileobj(fd, bucket_name, object_name)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "UploadFileObj"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_download_file(self) -> None:
        object_name = "aws_key_name"
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)
        self.s3.upload_file(upload_filename, bucket_name, object_name)

        with tracer.start_as_current_span("test"):
            self.s3.download_file(bucket_name, object_name, download_target_filename)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "DownloadFile"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_download_file_obj(self) -> None:
        object_name = "aws_key_name"
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)
        self.s3.upload_file(upload_filename, bucket_name, object_name)

        with tracer.start_as_current_span("test"):
            with open(download_target_filename, "wb") as fd:
                self.s3.download_fileobj(bucket_name, object_name, fd)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "DownloadFileObj"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"

    def test_s3_list_obj(self) -> None:
        bucket_name = "aws_bucket_name"

        self.s3.create_bucket(Bucket=bucket_name)

        with tracer.start_as_current_span("test"):
            self.s3.list_objects(Bucket=bucket_name)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        filter = lambda span: span.n == "sdk"  # noqa: E731
        test_span = get_first_span_by_filter(spans, filter)
        assert test_span

        filter = lambda span: span.n == "s3"  # noqa: E731
        s3_span = get_first_span_by_filter(spans, filter)
        assert s3_span

        assert s3_span.t == test_span.t
        assert s3_span.p == test_span.s

        assert not test_span.ec
        assert not s3_span.ec

        assert s3_span.data["s3"]["op"] == "ListObjects"
        assert s3_span.data["s3"]["bucket"] == "aws_bucket_name"
