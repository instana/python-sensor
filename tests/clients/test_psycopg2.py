# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import logging
import unittest
from ..helpers import testenv
from instana.singletons import tracer

import psycopg2
import psycopg2.extras
import psycopg2.extensions as ext

logger = logging.getLogger(__name__)


class TestPsycoPG2(unittest.TestCase):
    def setUp(self):
        deprecated_param_name = self.shortDescription() == 'test_deprecated_parameter_database'
        kwargs = {
            'host': testenv['postgresql_host'],
            'port': testenv['postgresql_port'],
            'user': testenv['postgresql_user'],
            'password': testenv['postgresql_pw'],
            'dbname' if not deprecated_param_name else 'database': testenv['postgresql_db'],
        }
        self.db = psycopg2.connect(**kwargs)

        database_setup_query = """
        DROP TABLE IF EXISTS users;
        CREATE TABLE users(
           id serial PRIMARY KEY,
           name VARCHAR (50),
           password VARCHAR (50),
           email VARCHAR (355),
           created_on TIMESTAMP,
           last_login TIMESTAMP
        );
        INSERT INTO users(name, email) VALUES('kermit', 'kermit@muppets.com');
        DROP FUNCTION IF EXISTS test_proc(VARCHAR(70));
        CREATE FUNCTION test_proc(candidate VARCHAR(70))
        RETURNS text AS $$
        BEGIN
            RETURN(SELECT name FROM users where email = candidate);
        END;
        $$ LANGUAGE plpgsql;
        """
        cursor = self.db.cursor()
        cursor.execute(database_setup_query)
        self.db.commit()
        cursor.close()


        self.cursor = self.db.cursor()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        if self.cursor and not self.cursor.connection.closed:
          self.cursor.close()
        if self.db and not self.db.closed:
          self.db.close()

    def test_vanilla_query(self):
        self.assertTrue(psycopg2.extras.register_uuid(None, self.db))
        self.assertTrue(psycopg2.extras.register_uuid(None, self.db.cursor()))

        self.cursor.execute("""SELECT * from users""")
        affected_rows = self.cursor.rowcount
        self.assertEqual(1, affected_rows)
        result = self.cursor.fetchone()

        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_basic_query(self):
        with tracer.start_active_span('test'):
            self.cursor.execute("""SELECT * from users""")
            affected_rows = self.cursor.rowcount
            result = self.cursor.fetchone()
            self.db.commit()

        self.assertEqual(1, affected_rows)
        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'SELECT * from users')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_basic_insert(self):
        with tracer.start_active_span('test'):
            self.cursor.execute("""INSERT INTO users(name, email) VALUES(%s, %s)""", ('beaker', 'beaker@muppets.com'))
            affected_rows = self.cursor.rowcount

        self.assertEqual(1, affected_rows)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_executemany(self):
        with tracer.start_active_span('test'):
            self.cursor.executemany("INSERT INTO users(name, email) VALUES(%s, %s)",
                                    [('beaker', 'beaker@muppets.com'), ('beaker', 'beaker@muppets.com')])
            affected_rows = self.cursor.rowcount
            self.db.commit()

        self.assertEqual(2, affected_rows)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

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

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'test_proc')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_error_capture(self):
        affected_rows = result = None
        try:
            with tracer.start_active_span('test'):
                self.cursor.execute("""SELECT * from blah""")
                affected_rows = self.cursor.rowcount
                self.cursor.fetchone()
        except Exception:
            pass

        self.assertIsNone(affected_rows)
        self.assertIsNone(result)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(1, db_span.ec)
        self.assertEqual(db_span.data["pg"]["error"], 'relation "blah" does not exist\nLINE 1: SELECT * from blah\n                      ^\n')

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'SELECT * from blah')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    # Added to validate unicode support and register_type.
    def test_unicode(self):
        ext.register_type(ext.UNICODE, self.cursor)
        snowman = "\u2603"

        self.cursor.execute("delete from users where id in (1,2,3)")

        # unicode in statement
        psycopg2.extras.execute_batch(self.cursor,
            "insert into users (id, name) values (%%s, %%s) -- %s" % snowman, [(1, 'x')])
        self.cursor.execute("select id, name from users where id = 1")
        self.assertEqual(self.cursor.fetchone(), (1, 'x'))

        # unicode in data
        psycopg2.extras.execute_batch(self.cursor,
            "insert into users (id, name) values (%s, %s)", [(2, snowman)])
        self.cursor.execute("select id, name from users where id = 2")
        self.assertEqual(self.cursor.fetchone(), (2, snowman))

        # unicode in both
        psycopg2.extras.execute_batch(self.cursor,
            "insert into users (id, name) values (%%s, %%s) -- %s" % snowman, [(3, snowman)])
        self.cursor.execute("select id, name from users where id = 3")
        self.assertEqual(self.cursor.fetchone(), (3, snowman))

    def test_register_type(self):
        import uuid

        oid1 = 2950
        oid2 = 2951

        ext.UUID = ext.new_type((oid1,), "UUID", lambda data, cursor: data and uuid.UUID(data) or None)
        ext.UUIDARRAY = ext.new_array_type((oid2,), "UUID[]", ext.UUID)

        ext.register_type(ext.UUID, self.cursor)
        ext.register_type(ext.UUIDARRAY, self.cursor)

    def test_connect_cursor_ctx_mgr(self):
        with tracer.start_active_span("test"):
            with self.db as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""SELECT * from users""")
                    affected_rows = cursor.rowcount
                    result = cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv["postgresql_db"])
        self.assertEqual(db_span.data["pg"]["user"], testenv["postgresql_user"])
        self.assertEqual(db_span.data["pg"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["pg"]["host"], testenv["postgresql_host"])
        self.assertEqual(db_span.data["pg"]["port"], testenv["postgresql_port"])

    def test_connect_ctx_mgr(self):
        with tracer.start_active_span("test"):
            with self.db as connection:
                cursor = connection.cursor()
                cursor.execute("""SELECT * from users""")
                affected_rows = cursor.rowcount
                result = cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv["postgresql_db"])
        self.assertEqual(db_span.data["pg"]["user"], testenv["postgresql_user"])
        self.assertEqual(db_span.data["pg"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["pg"]["host"], testenv["postgresql_host"])
        self.assertEqual(db_span.data["pg"]["port"], testenv["postgresql_port"])

    def test_cursor_ctx_mgr(self):
        with tracer.start_active_span("test"):
            connection = self.db
            with connection.cursor() as cursor:
                cursor.execute("""SELECT * from users""")
                affected_rows = cursor.rowcount
                result = cursor.fetchone()

        self.assertEqual(1, affected_rows)
        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv["postgresql_db"])
        self.assertEqual(db_span.data["pg"]["user"], testenv["postgresql_user"])
        self.assertEqual(db_span.data["pg"]["stmt"], "SELECT * from users")
        self.assertEqual(db_span.data["pg"]["host"], testenv["postgresql_host"])
        self.assertEqual(db_span.data["pg"]["port"], testenv["postgresql_port"])

    def test_deprecated_parameter_database(self):
        """test_deprecated_parameter_database"""

        with tracer.start_active_span('test'):
            self.cursor.execute("""SELECT * from users""")
            affected_rows = self.cursor.rowcount
            result = self.cursor.fetchone()
            self.db.commit()

        self.assertEqual(1, affected_rows)
        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span, test_span = spans

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertIsNone(db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
