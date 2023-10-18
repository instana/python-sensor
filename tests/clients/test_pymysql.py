# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import sys
import logging
import unittest
import pymysql
from ..helpers import testenv
from instana.singletons import tracer

logger = logging.getLogger(__name__)


class TestPyMySQL(unittest.TestCase):
    def setUp(self):
        deprecated_param_name = self.shortDescription() == 'test_deprecated_parameter_db'
        kwargs = {
            'host': testenv['mysql_host'],
            'port': testenv['mysql_port'],
            'user': testenv['mysql_user'],
            'passwd': testenv['mysql_pw'],
            'database' if not deprecated_param_name else 'db': testenv['mysql_db'],
        }
        self.db = pymysql.connect(**kwargs)

        database_setup_query = """
        DROP TABLE IF EXISTS users; |
        CREATE TABLE users(
            id serial primary key,
            name varchar(40) NOT NULL,
            email varchar(40) NOT NULL
        ); |
        INSERT INTO users(name, email) VALUES('kermit', 'kermit@muppets.com'); |
        DROP PROCEDURE IF EXISTS test_proc; |
        CREATE PROCEDURE test_proc(IN t VARCHAR(255))
        BEGIN
            SELECT name FROM users WHERE name = t;
        END
        """
        setup_cursor = self.db.cursor()
        for s in database_setup_query.split('|'):
          setup_cursor.execute(s)

        self.cursor = self.db.cursor()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        if self.cursor and self.cursor.connection.open:
          self.cursor.close()
        if self.db and self.db.open:
          self.db.close()

    def test_vanilla_query(self):
        affected_rows = self.cursor.execute("""SELECT * from users""")
        self.assertEqual(1, affected_rows)
        result = self.cursor.fetchone()
        self.assertEqual(3, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_basic_query(self):
        with tracer.start_active_span('test'):
            affected_rows = self.cursor.execute("""SELECT * from users""")
            result = self.cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(3, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'SELECT * from users')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_query_with_params(self):
        with tracer.start_active_span('test'):
            affected_rows = self.cursor.execute("""SELECT * from users where id=1""")
            result = self.cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(3, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'SELECT * from users where id=?')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_basic_insert(self):
        with tracer.start_active_span('test'):
            affected_rows = self.cursor.execute(
                        """INSERT INTO users(name, email) VALUES(%s, %s)""",
                        ('beaker', 'beaker@muppets.com'))

        self.assertEqual(1, affected_rows)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_executemany(self):
        with tracer.start_active_span('test'):
            affected_rows  = self.cursor.executemany("INSERT INTO users(name, email) VALUES(%s, %s)",
                                             [('beaker', 'beaker@muppets.com'), ('beaker', 'beaker@muppets.com')])
            self.db.commit()

        self.assertEqual(2, affected_rows)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_call_proc(self):
        with tracer.start_active_span('test'):
            callproc_result = self.cursor.callproc('test_proc', ('beaker',))

        self.assertIsInstance(callproc_result, tuple)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'test_proc')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_error_capture(self):
        affected_rows = None
        try:
            with tracer.start_active_span('test'):
                affected_rows = self.cursor.execute("""SELECT * from blah""")
        except Exception:
            pass

        self.assertIsNone(affected_rows)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)
        self.assertEqual(1, db_span.ec)

        self.assertEqual(db_span.data["mysql"]["error"], u'(1146, "Table \'%s.blah\' doesn\'t exist")' % testenv['mysql_db'])

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])
        self.assertEqual(db_span.data["mysql"]["user"], testenv['mysql_user'])
        self.assertEqual(db_span.data["mysql"]["stmt"], 'SELECT * from blah')
        self.assertEqual(db_span.data["mysql"]["host"], testenv['mysql_host'])
        self.assertEqual(db_span.data["mysql"]["port"], testenv['mysql_port'])

    def test_connect_cursor_ctx_mgr(self):
        with tracer.start_active_span("test"):
            with self.db as connection:
                with connection.cursor() as cursor:
                    affected_rows = cursor.execute("""SELECT * from users""")

        self.assertEqual(1, affected_rows)
        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv["mysql_db"])
        self.assertEqual(db_span.data["mysql"]["user"], testenv["mysql_user"])
        self.assertEqual(db_span.data["mysql"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["mysql"]["host"], testenv["mysql_host"])
        self.assertEqual(db_span.data["mysql"]["port"], testenv["mysql_port"])

    def test_connect_ctx_mgr(self):
        with tracer.start_active_span("test"):
            with self.db as connection:
                cursor = connection.cursor()
                cursor.execute("""SELECT * from users""")

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv["mysql_db"])
        self.assertEqual(db_span.data["mysql"]["user"], testenv["mysql_user"])
        self.assertEqual(db_span.data["mysql"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["mysql"]["host"], testenv["mysql_host"])
        self.assertEqual(db_span.data["mysql"]["port"], testenv["mysql_port"])

    def test_cursor_ctx_mgr(self):
        with tracer.start_active_span("test"):
            connection = self.db
            with connection.cursor() as cursor:
                cursor.execute("""SELECT * from users""")


        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv["mysql_db"])
        self.assertEqual(db_span.data["mysql"]["user"], testenv["mysql_user"])
        self.assertEqual(db_span.data["mysql"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["mysql"]["host"], testenv["mysql_host"])
        self.assertEqual(db_span.data["mysql"]["port"], testenv["mysql_port"])

    def test_deprecated_parameter_db(self):
        """test_deprecated_parameter_db"""

        with tracer.start_active_span('test'):
            affected_rows = self.cursor.execute("""SELECT * from users""")
            result = self.cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(3, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "mysql")
        self.assertEqual(db_span.data["mysql"]["db"], testenv['mysql_db'])