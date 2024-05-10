# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017

import unittest
import instana


class TestIdManagement(unittest.TestCase):
    def test_id_generation(self):
        count = 0
        while count <= 10000:
            id = instana.util.ids.generate_id()
            base10_id = int(id, 16)
            self.assertGreaterEqual(base10_id, 0)
            self.assertLessEqual(base10_id, 18446744073709551615)
            count += 1


    def test_various_header_to_id_conversion(self):
        # Get a hex string to test against & convert
        header_id = instana.util.ids.generate_id()
        converted_id = instana.util.ids.header_to_long_id(header_id)
        self.assertEqual(header_id, converted_id)

        # Hex value - result should be left padded
        result = instana.util.ids.header_to_long_id('abcdef')
        self.assertEqual('0000000000abcdef', result)

        # Hex value
        result = instana.util.ids.header_to_long_id('0123456789abcdef')
        self.assertEqual('0123456789abcdef', result)

        # Very long incoming header should just return the rightmost 16 bytes
        result = instana.util.ids.header_to_long_id('0x0123456789abcdef0123456789abcdef')
        self.assertEqual('0x0123456789abcdef0123456789abcdef', result)


    def test_header_to_id_conversion_with_bogus_header(self):
        # Bogus nil arg
        bogus_result = instana.util.ids.header_to_long_id(None)
        self.assertEqual(instana.util.ids.BAD_ID, bogus_result)

        # Bogus Integer arg
        bogus_result = instana.util.ids.header_to_long_id(1234)
        self.assertEqual(instana.util.ids.BAD_ID, bogus_result)

        # Bogus Array arg
        bogus_result = instana.util.ids.header_to_long_id([1234])
        self.assertEqual(instana.util.ids.BAD_ID, bogus_result)

        # Bogus Hex Values in String
        bogus_result = instana.util.ids.header_to_long_id('0xZZZZZZ')
        self.assertEqual(instana.util.ids.BAD_ID, bogus_result)

        bogus_result = instana.util.ids.header_to_long_id('ZZZZZZ')
        self.assertEqual(instana.util.ids.BAD_ID, bogus_result)
