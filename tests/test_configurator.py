from __future__ import absolute_import

import unittest

from instana.configurator import config


class TestRedis(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_has_default_config(self):
        self.assertEqual(config['asyncio_task_context_propagation']['enabled'], False)