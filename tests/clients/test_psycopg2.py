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

create_table_query = """
CREATE TABLE IF NOT EXISTS users(
   id serial PRIMARY KEY,
   name VARCHAR (50),
   password VARCHAR (50),
   email VARCHAR (355),
   created_on TIMESTAMP,
   last_login TIMESTAMP
);
"""

create_proc_query = """\
CREATE OR REPLACE FUNCTION test_proc(candidate VARCHAR(70)) 
RETURNS text AS $$
BEGIN
    RETURN(SELECT name FROM users where email = candidate);
END;
$$ LANGUAGE plpgsql;
"""

drop_proc_query = "DROP FUNCTION IF EXISTS test_proc(VARCHAR(70));"

db = psycopg2.connect(host=testenv['postgresql_host'], port=testenv['postgresql_port'],
                     user=testenv['postgresql_user'], password=testenv['postgresql_pw'],
                     database=testenv['postgresql_db'])

cursor = db.cursor()
cursor.execute(create_table_query)
cursor.execute(drop_proc_query)
cursor.execute(create_proc_query)
db.commit()
cursor.close()
db.close()


class TestPsycoPG2(unittest.TestCase):
    def setUp(self):
        self.db = psycopg2.connect(host=testenv['postgresql_host'], port=testenv['postgresql_port'],
                                   user=testenv['postgresql_user'], password=testenv['postgresql_pw'],
                                   database=testenv['postgresql_db'])
        self.cursor = self.db.cursor()
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_query(self):
        assert psycopg2.extras.register_uuid(None, self.db)
        assert psycopg2.extras.register_uuid(None, self.db.cursor())

        self.cursor.execute("""SELECT * from users""")
        result = self.cursor.fetchone()

        self.assertEqual(6, len(result))

        spans = self.recorder.queued_spans()
        self.assertEqual(0, len(spans))

    def test_basic_query(self):
        with tracer.start_active_span('test'):
            self.cursor.execute("""SELECT * from users""")
            self.cursor.fetchone()
            self.db.commit()

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'SELECT * from users')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_basic_insert(self):
        with tracer.start_active_span('test'):
            self.cursor.execute("""INSERT INTO users(name, email) VALUES(%s, %s)""", ('beaker', 'beaker@muppets.com'))

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_executemany(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.executemany("INSERT INTO users(name, email) VALUES(%s, %s)",
                                             [('beaker', 'beaker@muppets.com'), ('beaker', 'beaker@muppets.com')])
            self.db.commit()

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'INSERT INTO users(name, email) VALUES(%s, %s)')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_call_proc(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.callproc('test_proc', ('beaker',))

        assert(type(result) is tuple)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, db_span.t)
        self.assertEqual(db_span.p, test_span.s)

        self.assertEqual(None, db_span.ec)

        self.assertEqual(db_span.n, "postgres")
        self.assertEqual(db_span.data["pg"]["db"], testenv['postgresql_db'])
        self.assertEqual(db_span.data["pg"]["user"], testenv['postgresql_user'])
        self.assertEqual(db_span.data["pg"]["stmt"], 'test_proc')
        self.assertEqual(db_span.data["pg"]["host"], testenv['postgresql_host'])
        self.assertEqual(db_span.data["pg"]["port"], testenv['postgresql_port'])

    def test_error_capture(self):
        result = None
        try:
            with tracer.start_active_span('test'):
                result = self.cursor.execute("""SELECT * from blah""")
                self.cursor.fetchone()
        except Exception:
            pass

        assert(result is None)

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

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
        #
        # Python 2 chokes on Unicode and CircleCI tests are hanging (but pass locally).
        # Disable these tests for now as we want to really just test register_type
        # anyways
        #
        # snowman = "\u2603"
        #
        # self.cursor.execute("delete from users where id in (1,2,3)")
        #
        # # unicode in statement
        # psycopg2.extras.execute_batch(self.cursor,
        #     "insert into users (id, name) values (%%s, %%s) -- %s" % snowman, [(1, 'x')])
        # self.cursor.execute("select id, name from users where id = 1")
        # self.assertEqual(self.cursor.fetchone(), (1, 'x'))
        #
        # # unicode in data
        # psycopg2.extras.execute_batch(self.cursor,
        #     "insert into users (id, name) values (%s, %s)", [(2, snowman)])
        # self.cursor.execute("select id, name from users where id = 2")
        # self.assertEqual(self.cursor.fetchone(), (2, snowman))
        #
        # # unicode in both
        # psycopg2.extras.execute_batch(self.cursor,
        #     "insert into users (id, name) values (%%s, %%s) -- %s" % snowman, [(3, snowman)])
        # self.cursor.execute("select id, name from users where id = 3")
        # self.assertEqual(self.cursor.fetchone(), (3, snowman))

    def test_register_type(self):
        import uuid

        oid1 = 2950
        oid2 = 2951

        ext.UUID = ext.new_type((oid1,), "UUID", lambda data, cursor: data and uuid.UUID(data) or None)
        ext.UUIDARRAY = ext.new_array_type((oid2,), "UUID[]", ext.UUID)

        ext.register_type(ext.UUID, self.cursor)
        ext.register_type(ext.UUIDARRAY, self.cursor)

