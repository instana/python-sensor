# (c) Copyright IBM Corp. 2026

"""
Unit tests for AWSLambdaCollector.
This test suite validates the payload preparation and metric reporting
for the AWS Lambda instrumentation collector.
"""

from collections import defaultdict
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from instana.collector.aws_lambda import AWSLambdaCollector


class TestAWSLambdaCollector:
    """Test suite for AWSLambdaCollector base class."""

    @pytest.fixture(autouse=True)
    def _resource(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> Generator[None, None, None]:

        self.agent = MagicMock()
        self.collector = AWSLambdaCollector(self.agent)
        yield

    def test_prepare_payload_empty_span_queue(self) -> None:
        """Test that prepare_payload returns an empty list for spans when queue is empty."""
        payload = self.collector.prepare_payload()

        assert isinstance(payload, defaultdict)

        assert "spans" in payload
        assert payload["spans"] == []

        assert "metrics" in payload
        assert "plugins" in payload["metrics"]

    def test_prepare_payload_with_spans(self) -> None:
        """Test that prepare_payload formats queued spans and includes them in the payload."""
        mock_span = MagicMock()
        self.collector.span_queue.put(mock_span)

        # Mock queued_spans and format_span
        self.collector.queued_spans = MagicMock(return_value=[mock_span])

        with patch("instana.collector.aws_lambda.format_span") as mock_format:
            mock_format.return_value = [{"n": "test_span"}]
            payload = self.collector.prepare_payload()

        assert payload["spans"] == [{"n": "test_span"}]
        assert payload["metrics"]["plugins"] == []

    def test_prepare_payload_with_snapshot_data(self) -> None:
        """Test that prepare_payload includes snapshot data when it should be sent."""
        self.collector.snapshot_data = {
            "plugins": [{"name": "com.instana.plugin.aws.lambda"}]
        }
        self.collector.snapshot_data_sent = False

        payload = self.collector.prepare_payload()

        assert payload["metrics"] == {
            "plugins": [{"name": "com.instana.plugin.aws.lambda"}]
        }
        assert self.collector.snapshot_data_sent is True
