# (c) Copyright IBM Corp. 2024

from typing import Generator
from unittest.mock import Mock, patch

import pytest

from instana.recorder import StanRecorder
from instana.span.base_span import BaseSpan
from instana.span.span import InstanaSpan
from instana.span_context import SpanContext
from instana.util import DictionaryOfStan


def test_basespan(
    span: InstanaSpan,
    trace_id: int,
    span_id: int,
) -> None:
    base_span = BaseSpan(span, None)

    expected_dict = {
        "t": trace_id,
        "p": None,
        "s": span_id,
        "ts": round(span.start_time / 10**6),
        "d": None,
        "f": None,
        "ec": None,
        "data": DictionaryOfStan(),
        "stack": None,
    }

    assert expected_dict["t"] == base_span.t
    assert expected_dict["s"] == base_span.s
    assert expected_dict["p"] == base_span.p
    assert expected_dict["ts"] == base_span.ts
    assert expected_dict["d"] == base_span.d
    assert not base_span.f
    assert expected_dict["ec"] == base_span.ec
    assert isinstance(base_span.data, dict)
    assert expected_dict["stack"] == base_span.stack
    assert not base_span.sy

    expected_dict_str = str(expected_dict)
    assert expected_dict_str == repr(base_span)
    assert f"BaseSpan({expected_dict_str})" == str(base_span)


def test_basespan_with_synthetic_source_and_kwargs(
    span: InstanaSpan,
    trace_id: int,
    span_id: int,
) -> None:
    span.synthetic = True
    source = "source test"
    _kwarg1 = "value1"
    base_span = BaseSpan(span, source, arg1=_kwarg1)

    assert trace_id == base_span.t
    assert span_id == base_span.s
    # synthetic should be true only for entry spans
    assert not base_span.sy
    assert source == base_span.f
    assert _kwarg1 == base_span.arg1


def test_populate_extra_span_attributes(
    span: InstanaSpan,
) -> None:
    base_span = BaseSpan(span, None)
    base_span._populate_extra_span_attributes(span)

    assert not hasattr(base_span, "tp")
    assert not hasattr(base_span, "tp")
    assert not hasattr(base_span, "ia")
    assert not hasattr(base_span, "lt")
    assert not hasattr(base_span, "crtp")
    assert not hasattr(base_span, "crid")


def test_populate_extra_span_attributes_with_values(
    trace_id: int,
    span_id: int,
    span_processor: StanRecorder,
) -> None:
    long_id = 1512366075204170929049582354406559215
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        synthetic=True,
        trace_parent=True,
        instana_ancestor="IDK",
        long_trace_id=long_id,
        correlation_type="IDK",
        correlation_id=long_id,
    )
    span = InstanaSpan("test-base-span", span_context, span_processor)
    base_span = BaseSpan(span, None)
    base_span._populate_extra_span_attributes(span)

    assert trace_id == base_span.t
    assert span_id == base_span.s
    # synthetic should be true only for entry spans
    assert not base_span.sy
    assert base_span.tp
    assert "IDK" == base_span.ia
    assert long_id == base_span.lt
    assert "IDK" == base_span.crtp
    assert long_id == base_span.crid


def test_validate_attributes(
    base_span: BaseSpan,
) -> None:
    attributes = {
        "field1": 1,
        "field2": "two",
    }
    filtered_attributes = base_span._validate_attributes(attributes)

    assert isinstance(filtered_attributes, dict)
    assert len(attributes) == len(filtered_attributes)
    for key, value in attributes.items():
        assert key in filtered_attributes.keys()
        assert value in filtered_attributes.values()


def test_validate_attribute_with_invalid_key_type(
    base_span: BaseSpan,
) -> None:
    key = 1
    value = "one"

    (validated_key, validated_value) = base_span._validate_attribute(key, value)

    assert not validated_key
    assert not validated_value


def test_validate_attribute_exception(
    span: InstanaSpan,
) -> None:
    base_span = BaseSpan(span, None)
    key = "field1"
    value = span

    with patch(
        "instana.span.base_span.BaseSpan._convert_attribute_value",
        side_effect=Exception("mocked error"),
    ):
        (validated_key, validated_value) = base_span._validate_attribute(key, value)
        assert key == validated_key
        assert not validated_value


def test_convert_attribute_value(
    span: InstanaSpan,
) -> None:
    base_span = BaseSpan(span, None)
    value = span

    converted_value = base_span._convert_attribute_value(value)
    assert "<instana.span.span.InstanaSpan object" in converted_value


def test_convert_attribute_value_exception(
    base_span: BaseSpan,
) -> None:
    mock = Mock()
    mock.__repr__ = Mock(side_effect=Exception("mocked error"))

    converted_value = base_span._convert_attribute_value(mock)
    assert not converted_value
