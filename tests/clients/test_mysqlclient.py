# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys
import logging
import unittest
from ..helpers import testenv
from unittest import SkipTest
from instana.singletons import tracer


if sys.version_info[0] > 2:
    import MySQLdb
else:
    raise SkipTest("mysqlclient supported on Python 3 only")

logger = logging.getLogger(__name__)

create_table_query = 'CREATE TABLE IF NOT EXISTS users(id serial primary key, \
                      name varchar(40) NOT NULL, email varchar(40) NOT NULL)'

create_proc_query = """
CREATE PROCEDURE test_proc(IN t VARCHAR(255))
BEGIN
    SELECT name FROM users WHERE name = t;
END
"""

db = MySQLdb.connect(host=testenv['mysql_host'], port=testenv['mysql_port'],
                     user=testenv['mysql_user'], passwd=testenv['mysql_pw'],
                     db=testenv['mysql_db'])

cursor = db.cursor()
cursor.execute(create_table_query)

while cursor.nextset() is not None:
    pass

cursor.execute('DROP PROCEDURE IF EXISTS test_proc')

while cursor.nextset() is not None:
    pass

cursor.execute(create_proc_query)

while cursor.nextset() is not None:
    pass

cursor.close()
db.close()


class TestMySQLPython(unittest.TestCase):
    def setUp(self):
        self.db = MySQLdb.connect(host=testenv['mysql_host'], port=testenv['mysql_port'],
                                  user=testenv['mysql_user'], passwd=testenv['mysql_pw'],
                                  db=testenv['mysql_db'])
        self.cursor = self.db.cursor()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_query(self):
        self.cursor.execute("""SELECT * from users""")
        result = self.cursor.fetchone()
        self.assertEqual(3, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_basic_query(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.execute("""SELECT * from users""")
            self.cursor.fetchone()

        assert(result >= 0)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'SELECT * from users')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_basic_insert(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.execute(
                        """INSERT INTO users(name, email) VALUES(%s, %s)""",
                        ('beaker', 'beaker@muppets.com'))

        self.assertEqual(1, result)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_executemany(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.executemany("INSERT INTO users(name, email) VALUES(%s, %s)",
                                             [('beaker', 'beaker@muppets.com'), ('beaker', 'beaker@muppets.com')])
            self.db.commit()

        self.assertEqual(2, result)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_call_proc(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.callproc('test_proc', ('beaker',))

        assert(result)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'test_proc')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_error_capture(self):
        result = None
        span = None
        try:
            with tracer.start_active_span('test'):
                result = self.cursor.execute("""SELECT * from blah""")
                self.cursor.fetchone()
        except Exception:
            pass
        finally:
            if span:
                span.finish()

        assert(result is None)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(1, db_span.ec)
        self.assertEqual(db_span.data["mysql"]["error"], '(1146, "Table \'%s.blah\' doesn\'t exist")' % testenv['mysql_db'])

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'SELECT * from blah')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])
