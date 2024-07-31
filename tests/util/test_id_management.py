# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017

import pytest
from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID

import instana


def test_id_generation():
    count = 0
    while count <= 10000:
        id = instana.util.ids.generate_id()
        assert id >= 0
        assert id > INVALID_SPAN_ID
        assert id <= _SPAN_ID_MAX_VALUE
        count += 1


@pytest.mark.parametrize(
    "str_id, id",
    [
        ("BADCAFFE", 3135025150),
        ("abcdef", 11259375),
        ("0123456789abcdef", 81985529216486895),
        ("0x0123456789abcdef0123456789abcdef", 1512366075204170929049582354406559215),
        (None, INVALID_SPAN_ID),
        (1234, INVALID_SPAN_ID),
        ([1234], INVALID_SPAN_ID),
        ("0xZZZZZZ", INVALID_SPAN_ID),
        ("ZZZZZZ", INVALID_SPAN_ID),
        (b"BADCAFFE", 3135025150),
        (b"abcdef", 11259375),
        (b"0123456789abcdef", 81985529216486895),
        (b"0x0123456789abcdef0123456789abcdef", 1512366075204170929049582354406559215),
    ],
)
def test_header_to_long_id(str_id, id):
    result = instana.util.ids.header_to_long_id(str_id)
    assert result == id


@pytest.mark.parametrize(
    "str_id, id",
    [
        ("BADCAFFE", 3135025150),
        ("abcdef", 11259375),
        ("0123456789abcdef", 81985529216486895),
        ("0x0123456789abcdef0123456789abcdef", 81985529216486895),
        (None, INVALID_SPAN_ID),
        (1234, INVALID_SPAN_ID),
        ([1234], INVALID_SPAN_ID),
        ("0xZZZZZZ", INVALID_SPAN_ID),
        ("ZZZZZZ", INVALID_SPAN_ID),
        (b"BADCAFFE", 3135025150),
        (b"abcdef", 11259375),
        (b"0123456789abcdef", 81985529216486895),
        (b"0x0123456789abcdef0123456789abcdef", 81985529216486895),
    ],
)
def test_header_to_id(str_id, id):
    result = instana.util.ids.header_to_id(str_id)
    assert result == id
