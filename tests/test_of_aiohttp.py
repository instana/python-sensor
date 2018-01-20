from __future__ import absolute_import
import aiohttp
import async_timeout
import asyncio
from nose.tools import assert_equals
from instana import internal_tracer as tracer

class TestAiohttp:


    def setUp(self):
        """ Clear all spans before a test run """
        self.clientSession =  aiohttp.ClientSession()

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_basics(self):
        assert(self.clientSession)




