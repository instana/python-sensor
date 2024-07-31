# (c) Copyright IBM Corp. 2024

import unittest
from instana.util import validate_url


class TestUtil(unittest.TestCase):
    def test_validate_url(self):
        self.assertTrue(validate_url("http://localhost:3000"))
        self.assertTrue(validate_url("http://localhost:3000/"))
        self.assertTrue(validate_url("https://localhost:3000/path/item"))
        self.assertTrue(validate_url("http://localhost"))
        self.assertTrue(validate_url("https://localhost/"))
        self.assertTrue(validate_url("https://localhost/path/item"))
        self.assertTrue(validate_url("http://127.0.0.1"))
        self.assertTrue(validate_url("https://10.0.12.221/"))
        self.assertTrue(validate_url("http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/"))
        self.assertTrue(validate_url("https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443/"))
        self.assertFalse(validate_url("boligrafo"))
        self.assertFalse(validate_url("http:boligrafo"))
        self.assertFalse(validate_url(None))
