import string
import sys
import instana.util

if sys.version_info.major == 2:
    string_types = basestring
else:
    string_types = str


def test_id_generation():
    count = 0
    while count <= 10000:
        id = instana.util.generate_id()
        base10_id = int(id, 16)
        assert base10_id >= 0
        assert base10_id <= 18446744073709551615
        count += 1


def test_various_header_to_id_conversion():
    # Get a hex string to test against & convert
    header_id = instana.util.generate_id()
    converted_id = instana.util.header_to_id(header_id)
    assert(header_id == converted_id)

    # Hex value - result should be left padded
    result = instana.util.header_to_id('abcdef')
    assert('0000000000abcdef' == result)

    # Hex value
    result = instana.util.header_to_id('0123456789abcdef')
    assert('0123456789abcdef' == result)

    # Very long incoming header should just return the rightmost 16 bytes
    result = instana.util.header_to_id('0x0123456789abcdef0123456789abcdef')
    assert('0123456789abcdef' == result)


def test_header_to_id_conversion_with_bogus_header():
    # Bogus nil arg
    bogus_result = instana.util.header_to_id(None)
    assert(instana.util.BAD_ID == bogus_result)

    # Bogus Integer arg
    bogus_result = instana.util.header_to_id(1234)
    assert(instana.util.BAD_ID == bogus_result)

    # Bogus Array arg
    bogus_result = instana.util.header_to_id([1234])
    assert(instana.util.BAD_ID == bogus_result)

    # Bogus Hex Values in String
    bogus_result = instana.util.header_to_id('0xZZZZZZ')
    assert(instana.util.BAD_ID == bogus_result)

    bogus_result = instana.util.header_to_id('ZZZZZZ')
    assert(instana.util.BAD_ID == bogus_result)
