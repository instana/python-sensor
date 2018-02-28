from __future__ import absolute_import
import asyncio
import aiomysql
import instana.instrumentation


class TestAiomysql:

    def setUp(self):
        """ Clear all spans before a test run """
        self.connection = aiomysql.connect(host='localhost', port=3306,  user='root', password='', db='mysql', loop=None)



    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_basics(self):
        assert(self.connection)
