from __future__ import absolute_import

import logging

from nose.tools import assert_equals

from instana.singletons import tracer

from .helpers import testenv

import psycopg2

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
RETURNS void AS $$
BEGIN
    SELECT * FROM users where email = candidate;
END;
$$ LANGUAGE plpgsql;
"""

db = psycopg2.connect(host=testenv['postgresql_host'], port=testenv['postgresql_port'],
                     user=testenv['postgresql_user'], password=testenv['postgresql_pw'],
                     database=testenv['postgresql_db'])

cursor = db.cursor()
cursor.execute(create_table_query)
cursor.execute(create_proc_query)
db.commit()
cursor.close()
db.close()


class TestPsycoPG2:
    def setUp(self):
        logger.warn("Postgresql connecting: %s:<pass>@%s:5432/%s", testenv['postgresql_user'], testenv['postgresql_host'], testenv['postgresql_db'])
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
        self.cursor.execute("""SELECT * from users""")
        result = self.cursor.fetchone()
        assert_equals(3, len(result))

        spans = self.recorder.queued_spans()
        assert_equals(0, len(spans))

    def test_basic_query(self):
        with tracer.start_active_span('test'):
            self.cursor.execute("""SELECT * from users""")
            self.cursor.fetchone()
            self.db.commit()

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(None, db_span.error)
        assert_equals(None, db_span.ec)

        assert_equals(db_span.n, "postgres")
        assert_equals(db_span.data.pg.db, testenv['postgresql_db'])
        assert_equals(db_span.data.pg.user, testenv['postgresql_user'])
        assert_equals(db_span.data.pg.stmt, 'SELECT * from users')
        assert_equals(db_span.data.pg.host, "%s:5432" % testenv['postgresql_host'])

    def test_basic_insert(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.execute(
                        """INSERT INTO users(name, email) VALUES(%s, %s)""",
                        ('beaker', 'beaker@muppets.com'))

        assert_equals(1, result)

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(None, db_span.error)
        assert_equals(None, db_span.ec)

        assert_equals(db_span.n, "postgres")
        assert_equals(db_span.data.pg.db, testenv['postgresql_db'])
        assert_equals(db_span.data.pg.user, testenv['postgresql_user'])
        assert_equals(db_span.data.pg.stmt, 'INSERT INTO users(name, email) VALUES(%s, %s)')
        assert_equals(db_span.data.pg.host, "%s:5432" % testenv['postgresql_host'])

    def test_executemany(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.executemany("INSERT INTO users(name, email) VALUES(%s, %s)",
                                             [('beaker', 'beaker@muppets.com'), ('beaker', 'beaker@muppets.com')])
            self.db.commit()

        assert_equals(2, result)

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(None, db_span.error)
        assert_equals(None, db_span.ec)

        assert_equals(db_span.n, "postgres")
        assert_equals(db_span.data.pg.db, testenv['postgresql_db'])
        assert_equals(db_span.data.pg.user, testenv['postgresql_user'])
        assert_equals(db_span.data.pg.stmt, 'INSERT INTO users(name, email) VALUES(%s, %s)')
        assert_equals(db_span.data.pg.host, "%s:5432" % testenv['postgresql_host'])

    def test_call_proc(self):
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.callproc('test_proc', ('beaker',))

        assert(result)

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(None, db_span.error)
        assert_equals(None, db_span.ec)

        assert_equals(db_span.n, "postgres")
        assert_equals(db_span.data.pg.db, testenv['postgresql_db'])
        assert_equals(db_span.data.pg.user, testenv['postgresql_user'])
        assert_equals(db_span.data.pg.stmt, 'test_proc')
        assert_equals(db_span.data.pg.host, "%s:5432" % testenv['postgresql_host'])

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
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(True, db_span.error)
        assert_equals(1, db_span.ec)
        assert_equals(db_span.data.pg.error, '(1146, "Table \'%s.blah\' doesn\'t exist")' % testenv['postgresql_db'])

        assert_equals(db_span.n, "postgres")
        assert_equals(db_span.data.pg.db, testenv['postgresql_db'])
        assert_equals(db_span.data.pg.user, testenv['postgresql_user'])
        assert_equals(db_span.data.pg.stmt, 'SELECT * from blah')
        assert_equals(db_span.data.pg.host, "%s:5432" % testenv['postgresql_host'])
