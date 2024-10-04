# (c) Copyright IBM Corp. 2024

from typing import Generator, Tuple

import pytest

from instana.recorder import StanRecorder
from instana.span.sdk_span import SDKSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext


class TestSDKSpan:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.span = None
        yield

    def test_sdkspan(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
    ) -> None:
        span_name = "test-sdk-span"
        service_name = "test-sdk"
        attributes = {
            "span.kind": "entry",
            "arguments": "--quiet",
            "return": "True",
        }
        self.span = InstanaSpan(
            span_name, span_context, span_processor, attributes=attributes
        )
        sdk_span = SDKSpan(self.span, None, service_name)

        expected_result = {
            "n": "sdk",
            "k": 1,
            "data": {
                "service": service_name,
                "sdk": {
                    "name": span_name,
                    "type": attributes["span.kind"],
                    "custom": {
                        "attributes": attributes,
                    },
                    "arguments": attributes["arguments"],
                    "return": attributes["return"],
                },
            },
        }

        assert expected_result["n"] == sdk_span.n
        assert expected_result["k"] == sdk_span.k
        assert len(expected_result["data"]) == len(sdk_span.data)
        assert expected_result["data"]["service"] == sdk_span.data["service"]
        assert len(expected_result["data"]["sdk"]) == len(sdk_span.data["sdk"])
        assert expected_result["data"]["sdk"]["name"] == sdk_span.data["sdk"]["name"]
        assert expected_result["data"]["sdk"]["type"] == sdk_span.data["sdk"]["type"]
        assert len(attributes) == len(sdk_span.data["sdk"]["custom"]["tags"])
        assert attributes == sdk_span.data["sdk"]["custom"]["tags"]
        assert attributes["arguments"] == sdk_span.data["sdk"]["arguments"]
        assert attributes["return"] == sdk_span.data["sdk"]["return"]

    @pytest.mark.parametrize(
        "span_kind, expected_result",
        [
            (None, ("intermediate", 3)),
            ("entry", ("entry", 1)),
            ("server", ("entry", 1)),
            ("consumer", ("entry", 1)),
            ("exit", ("exit", 2)),
            ("client", ("exit", 2)),
            ("producer", ("exit", 2)),
        ],
    )
    def test_sdkspan_get_span_kind(
        self,
        span_context: SpanContext,
        span_processor: StanRecorder,
        span_kind: str,
        expected_result: Tuple[str, int],
    ) -> None:
        attributes = {
            "span.kind": span_kind,
        }
        self.span = InstanaSpan(
            "test-sdk-span", span_context, span_processor, attributes=attributes
        )
        sdk_span = SDKSpan(self.span, None, "test")

        kind = sdk_span.get_span_kind(self.span)

        assert expected_result == kind

    def test_sdkspan_get_span_kind_with_no_attributes(
        self,
        span: InstanaSpan,
    ) -> None:
        self.span = SDKSpan(span, None, "test")
        kind = self.span.get_span_kind(span)
        assert ("intermediate", 3) == kind
