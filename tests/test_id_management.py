import string
import sys

from nose.tools import assert_equals

import instana.util

if sys.version_info.major is 2:
    string_types = basestring
else:
    string_types = str


def test_id_generation():
    count = 0
    while count <= 1000:
        id = instana.util.generate_id()
        assert id >= -9223372036854775808
        assert id <= 9223372036854775807
        count += 1


def test_id_max_value_and_conversion():
    max_id = 9223372036854775807
    min_id = -9223372036854775808
    max_hex = "7fffffffffffffff"
    min_hex = "8000000000000000"

    assert_equals(max_hex, instana.util.id_to_header(max_id))
    assert_equals(min_hex, instana.util.id_to_header(min_id))

    assert_equals(max_id, instana.util.header_to_id(max_hex))
    assert_equals(min_id, instana.util.header_to_id(min_hex))


def test_id_conversion_back_and_forth():
    # id --> header --> id
    original_id = instana.util.generate_id()
    header_id = instana.util.id_to_header(original_id)
    converted_back_id = instana.util.header_to_id(header_id)
    assert original_id == converted_back_id

    # header --> id --> header
    original_header_id = "c025ee93b1aeda7b"
    id = instana.util.header_to_id(original_header_id)
    converted_back_header_id = instana.util.id_to_header(id)
    assert_equals(original_header_id, converted_back_header_id)

    # Test a random value
    id = -7815363404733516491
    header = "938a406416457535"

    result = instana.util.header_to_id(header)
    assert_equals(id, result)

    result = instana.util.id_to_header(id)
    assert_equals(header, result)


def test_that_leading_zeros_handled_correctly():
    header = instana.util.id_to_header(16)
    assert_equals("10", header)

    id = instana.util.header_to_id("10")
    assert_equals(16, id)

    id = instana.util.header_to_id("0000000000000010")
    assert_equals(16, id)

    id = instana.util.header_to_id("88b6c735206ca42")
    assert_equals(615705016619420226, id)

    id = instana.util.header_to_id("088b6c735206ca42")
    assert_equals(615705016619420226, id)


def test_id_to_header_conversion():
    # Test passing a standard Integer ID
    original_id = instana.util.generate_id()
    converted_id = instana.util.id_to_header(original_id)

    # Assert that it is a string and there are no non-hex characters
    assert isinstance(converted_id, string_types)
    assert all(c in string.hexdigits for c in converted_id)

    # Test passing a standard Integer ID as a String
    original_id = instana.util.generate_id()
    converted_id = instana.util.id_to_header(original_id)

    # Assert that it is a string and there are no non-hex characters
    assert isinstance(converted_id, string_types)
    assert all(c in string.hexdigits for c in converted_id)


def test_id_to_header_conversion_with_bogus_id():
    # Test passing an empty String
    converted_id = instana.util.id_to_header('')

    # Assert that it is a string and there are no non-hex characters
    assert isinstance(converted_id, string_types)
    assert converted_id == instana.util.BAD_ID_HEADER

    # Test passing a nil
    converted_id = instana.util.id_to_header(None)

    # Assert that it is a string and there are no non-hex characters
    assert isinstance(converted_id, string_types)
    assert converted_id == instana.util.BAD_ID_HEADER

    # Test passing an Array
    converted_id = instana.util.id_to_header([])

    # Assert that it is a string and there are no non-hex characters
    assert isinstance(converted_id, string_types)
    assert converted_id == instana.util.BAD_ID_HEADER


def test_header_to_id_conversion():
    # Get a hex string to test against & convert
    header_id = instana.util.id_to_header(instana.util.generate_id)
    converted_id = instana.util.header_to_id(header_id)

    # Assert that it is an Integer
    assert isinstance(converted_id, int)


def test_header_to_id_conversion_with_bogus_header():
    # Bogus nil arg
    bogus_result = instana.util.header_to_id(None)
    assert_equals(instana.util.BAD_ID_LONG, bogus_result)

    # Bogus Integer arg
    bogus_result = instana.util.header_to_id(1234)
    assert_equals(instana.util.BAD_ID_LONG, bogus_result)

    # Bogus Array arg
    bogus_result = instana.util.header_to_id([1234])
    assert_equals(instana.util.BAD_ID_LONG, bogus_result)
