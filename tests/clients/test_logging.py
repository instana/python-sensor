# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
import unittest
from unittest.mock import patch

from opentelemetry.trace import SpanKind

import pytest
from instana.singletons import agent, tracer

class TestLogging(unittest.TestCase):

    @pytest.fixture
    def capture_log(self, caplog):
        self.caplog = caplog

    def setUp(self) -> None:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.logger = logging.getLogger("unit test")

    def tearDown(self) -> None:
        """Ensure that allow_exit_as_root has the default value"""
        agent.options.allow_exit_as_root = False

    def test_no_span(self) -> None:
        self.logger.setLevel(logging.INFO)
        with tracer.start_as_current_span("test"):
            self.logger.info("info message")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

    def test_extra_span(self) -> None:
        with tracer.start_as_current_span("test"):
            self.logger.warning("foo %s", "bar")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        assert spans[0].k is SpanKind.CLIENT

        assert spans[0].data["log"].get("message") == "foo bar"

    def test_log_with_tuple(self) -> None:
        with tracer.start_as_current_span("test"):
            self.logger.warning("foo %s", ("bar",))

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        assert spans[0].k is SpanKind.CLIENT

        assert spans[0].data["log"].get("message") == "foo ('bar',)"

    def test_log_with_dict(self) -> None:
        with tracer.start_as_current_span("test"):
            self.logger.warning("foo %s", {"bar": 18})

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        assert spans[0].k is SpanKind.CLIENT

        assert spans[0].data["log"].get("message") == "foo {'bar': 18}"

    def test_parameters(self) -> None:
        with tracer.start_as_current_span("test"):
            try:
                a = 42
                b = 0
                c = a / b
            except Exception as e:
                self.logger.exception("Exception: %s", str(e))

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        assert spans[0].data["log"].get("parameters") is not None

    def test_no_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.logger.info("info message")

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.logger.warning("foo %s", "bar")

        spans = self.recorder.queued_spans()
        assert len(spans) == 1
        assert spans[0].k is SpanKind.CLIENT

        assert spans[0].data["log"].get("message") == "foo bar"

    def test_exception(self) -> None:
        with tracer.start_as_current_span("test"):
            with patch(
                "instana.span.span.InstanaSpan.add_event",
                side_effect=Exception("mocked error"),
            ):
                self.logger.warning("foo %s", "bar")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        assert spans[0].k is SpanKind.CLIENT

        assert spans[0].data["log"] == {}

    @pytest.mark.usefixtures("capture_log")
    def test_log_caller(self):
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("source: %(funcName)s, message: %(message)s")
        )
        self.logger.addHandler(handler)

        def log_custom_warning():
            self.logger.warning("foo %s", "bar")

        with tracer.start_active_span("test"):
            log_custom_warning()
        self.assertEqual(self.caplog.records[0].funcName, "log_custom_warning")

        self.logger.removeHandler(handler)
