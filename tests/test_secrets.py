from __future__ import absolute_import

import unittest

from instana.singletons import agent
from instana.util import strip_secrets


class TestSecrets(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_equals_ignore_case(self):
        matcher = 'equals-ignore-case'
        kwlist = ['two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals(self):
        matcher = 'equals'
        kwlist = ['Two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals_no_match(self):
        matcher = 'equals'
        kwlist = ['two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_contains_ignore_case(self):
        matcher = 'contains-ignore-case'
        kwlist = ['FI']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five=<redacted>")

    def test_contains_ignore_case_no_match(self):
        matcher = 'contains-ignore-case'
        kwlist = ['XXXXXX']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_contains(self):
        matcher = 'contains'
        kwlist = ['fi']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five=<redacted>")

    def test_contains_no_match(self):
        matcher = 'contains'
        kwlist = ['XXXXXX']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_regex(self):
        matcher = 'regex'
        kwlist = ['\d']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4=<redacted>&five='okyeah'")

    def test_regex_no_match(self):
        matcher = 'regex'
        kwlist = ['\d\d\d']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets(query_params, matcher, kwlist)

        self.assertEquals(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")
