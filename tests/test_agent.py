from __future__ import absolute_import

import unittest

from instana.singletons import agent, tracer
from instana.options import StandardOptions


class TestAgent(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_secrets(self):
        self.assertTrue(hasattr(agent, 'secrets_matcher'))
        self.assertEqual(agent.secrets_matcher, 'contains-ignore-case')
        self.assertTrue(hasattr(agent, 'secrets_list'))
        self.assertEqual(agent.secrets_list, ['key', 'pass', 'secret'])

    def test_has_extra_headers(self):
        self.assertTrue(hasattr(agent, 'extra_headers'))

    def test_has_options(self):
        self.assertTrue(hasattr(agent, 'options'))
        self.assertTrue(type(agent.options) is StandardOptions)

