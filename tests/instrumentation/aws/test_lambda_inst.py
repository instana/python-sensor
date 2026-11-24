# (c) Copyright IBM Corp. 2026

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from instana.instrumentation.aws import lambda_inst

TRACE_ID = 1812338823475918251
SERVER_TIMING = "intid;desc=1922fa4b3d1d76ab"


class TestLambdaHandlerServerTiming:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        self.agent = MagicMock()
        self.agent.collector.started = False
        self.agent.options.disable_server_timing = False
        self.span = MagicMock()
        self.span.context.trace_id = TRACE_ID
        tracer = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = self.span

        with (
            patch.object(lambda_inst, "get_agent", return_value=self.agent),
            patch("instana.singletons.get_agent", return_value=self.agent),
            patch.object(lambda_inst, "get_tracer", return_value=tracer),
            patch.object(lambda_inst, "get_context"),
            patch.object(lambda_inst, "enrich_lambda_span"),
            patch.object(
                lambda_inst, "define_server_timing", return_value=SERVER_TIMING
            ),
        ):
            yield

    def _invoke(self, result: Any) -> Any:
        handler = MagicMock(return_value=result)
        return lambda_inst.lambda_handler_with_instana(handler, None, ({}, {}), {})

    def test_headers_get_server_timing(self) -> None:
        result = self._invoke({"statusCode": 200, "headers": {}})
        assert result["headers"]["Server-Timing"] == SERVER_TIMING

    def test_multi_value_headers_get_server_timing(self) -> None:
        result = self._invoke({"statusCode": 200, "multiValueHeaders": {}})
        assert result["multiValueHeaders"]["Server-Timing"] == [SERVER_TIMING]

    def test_headers_untouched_when_disabled(self) -> None:
        self.agent.options.disable_server_timing = True
        result = self._invoke({"statusCode": 200, "headers": {}})
        assert "Server-Timing" not in result["headers"]

    def test_multi_value_headers_untouched_when_disabled(self) -> None:
        self.agent.options.disable_server_timing = True
        result = self._invoke({"statusCode": 200, "multiValueHeaders": {}})
        assert "Server-Timing" not in result["multiValueHeaders"]

    def test_status_code_still_recorded_when_disabled(self) -> None:
        self.agent.options.disable_server_timing = True
        self._invoke({"statusCode": 502, "headers": {}})
        self.span.set_attribute.assert_called_once()
        self.span.record_exception.assert_called_once_with("HTTP status 502")

    def test_non_dict_result_returned_unchanged(self) -> None:
        assert self._invoke("plain") == "plain"

    def test_handler_exception_is_recorded_and_raised(self) -> None:
        handler = MagicMock(side_effect=ValueError("boom"))
        with pytest.raises(ValueError):
            lambda_inst.lambda_handler_with_instana(handler, None, ({}, {}), {})
        self.span.record_exception.assert_called_once()
        self.agent.collector.shutdown.assert_called()
