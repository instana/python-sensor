# (c) Copyright IBM Corp. 2024

import logging
import queue
import threading
import time
from typing import Generator
from unittest.mock import patch

import pytest
from pytest import LogCaptureFixture

from instana.agent.host import HostAgent
from instana.collector.base import BaseCollector
from instana.recorder import StanRecorder
from instana.span.registered_span import RegisteredSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext


class TestBaseCollector:
    @pytest.fixture(autouse=True)
    def _resource(
        self,
        caplog: LogCaptureFixture,
    ) -> Generator[None, None, None]:
        self.collector = BaseCollector(HostAgent())
        yield
        self.collector.shutdown(report_final=False)
        self.collector = None
        caplog.clear()

    def test_default(self) -> None:
        assert isinstance(self.collector.agent, HostAgent)
        assert self.collector.THREAD_NAME == "Instana Collector"
        assert isinstance(self.collector.span_queue, queue.Queue)
        assert isinstance(self.collector.profile_queue, queue.Queue)
        assert not self.collector.reporting_thread
        assert isinstance(self.collector.thread_shutdown, threading.Event)
        assert self.collector.snapshot_data_last_sent == 0
        assert self.collector.snapshot_data_interval == 300
        assert len(self.collector.helpers) == 0
        assert self.collector.report_interval == 1
        assert not self.collector.started
        assert self.collector.fetching_start_time == 0

    def test_is_reporting_thread_running(self) -> None:
        stop_event = threading.Event()

        def reporting_function():
            stop_event.wait()

        sample_thread = threading.Thread(
            name=self.collector.THREAD_NAME, target=reporting_function
        )
        sample_thread.start()
        try:
            assert self.collector.is_reporting_thread_running()
        finally:
            stop_event.set()
            sample_thread.join()

    def test_is_reporting_thread_running_with_different_name(self) -> None:
        self.collector.THREAD_NAME = "sample-collector"
        stop_event = threading.Event()

        def reporting_function():
            stop_event.wait()

        sample_thread = threading.Thread(name="test-thread", target=reporting_function)
        sample_thread.start()
        try:
            assert not self.collector.is_reporting_thread_running()
        finally:
            stop_event.set()
            sample_thread.join()

    def test_start_collector_while_running_thread(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        with patch(
            "instana.collector.base.BaseCollector.is_reporting_thread_running",
            return_value=True,
        ):
            self.collector.start()
            assert (
                "BaseCollector.start non-fatal: call but thread already running (started: False)"
                in caplog.messages
            )

    def test_start_agent_shutdown_is_set(self) -> None:
        self.collector.thread_shutdown.set()
        isThreadFound = False
        with patch(
            "instana.collector.base.BaseCollector.is_reporting_thread_running",
            return_value=True,
        ):
            response = self.collector.start()
            assert not response
            for thread in threading.enumerate():
                if thread.name == "Collector Timed Start":
                    isThreadFound = True
            assert isThreadFound

    def test_start_collector_when_agent_is_ready(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        with patch(
            "instana.collector.base.BaseCollector.is_reporting_thread_running",
            return_value=False,
        ):
            if not self.collector.started:
                self.collector.start()
                assert self.collector.started
                assert self.collector.reporting_thread.daemon
                assert (
                    self.collector.reporting_thread.name == self.collector.THREAD_NAME
                )

    def test_start_agent_can_not_send(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        with patch(
            "instana.collector.base.BaseCollector.is_reporting_thread_running",
            return_value=False,
        ), patch("instana.agent.host.HostAgent.can_send", return_value=False):
            caplog.set_level(logging.WARNING, logger="instana")
            self.collector.agent.machine.fsm.current = "test"
            self.collector.start()
            assert (
                "BaseCollector.start: the agent tells us we can't send anything out"
                in caplog.messages
            )

    def test_shutdown(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        self.collector.shutdown()
        assert "Collector.shutdown: Reporting final data." in caplog.messages
        assert not self.collector.started

    def test_should_send_snapshot_data(self, caplog: LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        self.collector.should_send_snapshot_data()
        assert (
            "BaseCollector: should_send_snapshot_data needs to be overridden"
            in caplog.messages
        )

    def test_collect_snapshot(
        self,
        caplog: LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        self.collector.collect_snapshot()
        assert (
            "BaseCollector: collect_snapshot needs to be overridden" in caplog.messages
        )

    def test_queued_spans(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_list = [
            RegisteredSpan(
                InstanaSpan("span1", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span2", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span3", span_context, span_processor), None, "log"
            ),
        ]
        for span in span_list:
            self.collector.span_queue.put(span)
        time.sleep(0.1)
        spans = self.collector.queued_spans()
        assert len(spans) == 3

    def test_queued_profiles(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_list = [
            RegisteredSpan(
                InstanaSpan("span1", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span2", span_context, span_processor), None, "log"
            ),
            RegisteredSpan(
                InstanaSpan("span3", span_context, span_processor), None, "log"
            ),
        ]
        for span in span_list:
            self.collector.profile_queue.put(span)
        time.sleep(0.1)
        profiles = self.collector.queued_profiles()
        assert len(profiles) == 3
