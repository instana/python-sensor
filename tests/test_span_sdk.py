# (c) Copyright IBM Corp. 2024

from typing import Tuple

import pytest

from instana.span import InstanaSpan, SDKSpan
from instana.span_context import SpanContext


def test_sdkspan(span_context: SpanContext) -> None:
    span_name = "test-sdk-span"
    service_name = "test-sdk"
    attributes = {
        "span.kind": "entry",
        "arguments": "--quiet",
        "return": "True",
    }
    span = InstanaSpan(span_name, span_context, attributes=attributes)
    sdk_span = SDKSpan(span, None, service_name)

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
    assert len(attributes) == len(sdk_span.data["sdk"]["custom"]["attributes"])
    assert attributes == sdk_span.data["sdk"]["custom"]["attributes"]
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
    span_context: SpanContext,
    span_kind: str,
    expected_result: Tuple[str, int],
) -> None:
    attributes = {
        "span.kind": span_kind,
    }
    span = InstanaSpan("test-sdk-span", span_context, attributes=attributes)
    sdk_span = SDKSpan(span, None, "test")

    kind = sdk_span.get_span_kind(span)

    assert expected_result == kind


def test_sdkspan_get_span_kind_with_no_attributes(span: InstanaSpan) -> None:
    sdk_span = SDKSpan(span, None, "test")
    kind = sdk_span.get_span_kind(span)
    assert ("intermediate", 3) == kind
