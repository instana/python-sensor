from __future__ import absolute_import

import logging

from .helpers import testenv

import pymongo

logger = logging.getLogger(__name__)

class TestPyMongo:
    def setUp(self):
        logger.warn("Connecting to MongoDB mongo://%s:<pass>@%s:%s",
                    testenv['mongodb_user'], testenv['mongodb_host'], testenv['mongodb_port'])
        self.conn = pymongo.MongoClient(host=testenv['mongodb_host'], port=int(testenv['mongodb_port']),
                                        username=testenv['mongodb_user'], password=testenv['mongodb_pw'])

    def tearDown(self):
        return None

    def test_basic(self):
        pass
