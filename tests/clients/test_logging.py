# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
from typing import Generator
from unittest.mock import patch

import pytest
from opentelemetry.trace import SpanKind

from instana.singletons import agent, tracer

from opentelemetry.trace import SpanKind

from instana.singletons import agent, tracer


class TestLogging:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Clear all spans before a test run
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.logger = logging.getLogger("unit test")
        yield
        # tearDown
        # Ensure that allow_exit_as_root has the default value
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

    def test_log_with_dict(self) -> None:
        with tracer.start_as_current_span("test"):
            self.logger.warning("foo %s", {"bar": 18})

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))
        self.assertIs(SpanKind.CLIENT, spans[0].k)

        self.assertEqual("foo {'bar': 18}", spans[0].data["event"].get("message"))

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

    def test_log_caller(self, caplog: pytest.LogCaptureFixture) -> None:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("source: %(funcName)s, message: %(message)s")
        )
        self.logger.addHandler(handler)

        def log_custom_warning():
            self.logger.warning("foo %s", "bar")

        with tracer.start_as_current_span("test"):
            log_custom_warning()

        assert caplog.records[-1].funcName == "log_custom_warning"

        self.logger.removeHandler(handler)
