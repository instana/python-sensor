# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018

import unittest

from instana.util.secrets import strip_secrets_from_query


class TestSecrets(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_equals_ignore_case(self):
        matcher = 'equals-ignore-case'
        kwlist = ['two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals(self):
        matcher = 'equals'
        kwlist = ['Two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals_no_match(self):
        matcher = 'equals'
        kwlist = ['two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_contains_ignore_case(self):
        matcher = 'contains-ignore-case'
        kwlist = ['FI']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five=<redacted>")

    def test_contains_ignore_case_no_match(self):
        matcher = 'contains-ignore-case'
        kwlist = ['XXXXXX']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_contains(self):
        matcher = 'contains'
        kwlist = ['fi']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five=<redacted>")

    def test_contains_no_match(self):
        matcher = 'contains'
        kwlist = ['XXXXXX']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_regex(self):
        matcher = 'regex'
        kwlist = [r"\d"]

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4=<redacted>&five='okyeah'")

    def test_regex_no_match(self):
        matcher = 'regex'
        kwlist = [r"\d\d\d"]

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_equals_with_path_component(self):
        matcher = 'equals'
        kwlist = ['Two']

        query_params = "/signup?one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "/signup?one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals_with_full_url(self):
        matcher = 'equals'
        kwlist = ['Two']

        query_params = "http://www.x.org/signup?one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "http://www.x.org/signup?one=1&Two=<redacted>&THREE=&4='+'&five='okyeah'")

    def test_equals_with_none(self):
        matcher = 'equals'
        kwlist = ['Two']

        query_params = None

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual('', stripped)

    def test_bad_matcher(self):
        matcher = 'BADCAFE'
        kwlist = ['Two']

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")

    def test_bad_kwlist(self):
        matcher = 'equals'
        kwlist = None

        query_params = "one=1&Two=two&THREE=&4='+'&five='okyeah'"

        stripped = strip_secrets_from_query(query_params, matcher, kwlist)

        self.assertEqual(stripped, "one=1&Two=two&THREE=&4='+'&five='okyeah'")
