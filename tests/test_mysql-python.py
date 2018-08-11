from __future__ import absolute_import

import logging
import os
import sys
from unittest import SkipTest

from nose.tools import assert_equals

from instana.singletons import tracer

if sys.version_info < (3, 0):
    import MySQLdb
else:
    raise SkipTest("MySQL-python supported on Python 2.7 only")


logger = logging.getLogger(__name__)


if 'MYSQL_HOST' in os.environ:
    mysql_host = os.environ['MYSQL_HOST']
elif 'TRAVIS_MYSQL_HOST' in os.environ:
    mysql_host = os.environ['TRAVIS_MYSQL_HOST']
else:
    mysql_host = '127.0.0.1'

if 'MYSQL_PORT' in os.environ:
    mysql_port = int(os.environ['MYSQL_PORT'])
else:
    mysql_port = 3306

if 'MYSQL_DB' in os.environ:
    mysql_db = os.environ['MYSQL_DB']
else:
    mysql_db = "travis_ci_test"

if 'MYSQL_USER' in os.environ:
    mysql_user = os.environ['MYSQL_USER']
else:
    mysql_user = "root"

if 'MYSQL_PW' in os.environ:
    mysql_pw = os.environ['MYSQL_PW']
elif 'TRAVIS_MYSQL_PASS' in os.environ:
    mysql_pw = os.environ['TRAVIS_MYSQL_PASS']
else:
    mysql_pw = ''

create_table_query = 'CREATE TABLE IF NOT EXISTS users(id serial primary key, \
                      name varchar(40) NOT NULL, email varchar(40) NOT NULL)'

create_proc_query = """
CREATE PROCEDURE test_proc(IN t VARCHAR(255))
BEGIN
    SELECT name FROM users WHERE name = t;
END
"""

db = MySQLdb.connect(host=mysql_host, port=mysql_port,
                     user=mysql_user, passwd=mysql_pw,
                     db=mysql_db)

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


class TestMySQLPython:
    def setUp(self):
        logger.warn("MySQL connecting: %s:<pass>@%s:3306/%s", mysql_user, mysql_host, mysql_db)
        self.db = MySQLdb.connect(host=mysql_host, port=mysql_port,
                                  user=mysql_user, passwd=mysql_pw,
                                  db=mysql_db)
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
        result = None
        with tracer.start_active_span('test'):
            result = self.cursor.execute("""SELECT * from users""")
            self.cursor.fetchone()

        assert(result >= 0)

        spans = self.recorder.queued_spans()
        assert_equals(2, len(spans))

        db_span = spans[0]
        test_span = spans[1]

        assert_equals("test", test_span.data.sdk.name)
        assert_equals(test_span.t, db_span.t)
        assert_equals(db_span.p, test_span.s)

        assert_equals(None, db_span.error)
        assert_equals(None, db_span.ec)

        assert_equals(db_span.n, "mysql")
        assert_equals(db_span.data.mysql.db, mysql_db)
        assert_equals(db_span.data.mysql.user, mysql_user)
        assert_equals(db_span.data.mysql.stmt, 'SELECT * from users')
        assert_equals(db_span.data.mysql.host, "%s:3306" % mysql_host)

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

        assert_equals(db_span.n, "mysql")
        assert_equals(db_span.data.mysql.db, mysql_db)
        assert_equals(db_span.data.mysql.user, mysql_user)
        assert_equals(db_span.data.mysql.stmt, 'INSERT INTO users(name, email) VALUES(%s, %s)')
        assert_equals(db_span.data.mysql.host, "%s:3306" % mysql_host)

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

        assert_equals(db_span.n, "mysql")
        assert_equals(db_span.data.mysql.db, mysql_db)
        assert_equals(db_span.data.mysql.user, mysql_user)
        assert_equals(db_span.data.mysql.stmt, 'INSERT INTO users(name, email) VALUES(%s, %s)')
        assert_equals(db_span.data.mysql.host, "%s:3306" % mysql_host)

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

        assert_equals(db_span.n, "mysql")
        assert_equals(db_span.data.mysql.db, mysql_db)
        assert_equals(db_span.data.mysql.user, mysql_user)
        assert_equals(db_span.data.mysql.stmt, 'test_proc')
        assert_equals(db_span.data.mysql.host, "%s:3306" % mysql_host)

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
        assert_equals(db_span.data.mysql.error, '(1146, "Table \'%s.blah\' doesn\'t exist")' % mysql_db)

        assert_equals(db_span.n, "mysql")
        assert_equals(db_span.data.mysql.db, mysql_db)
        assert_equals(db_span.data.mysql.user, mysql_user)
        assert_equals(db_span.data.mysql.stmt, 'SELECT * from blah')
        assert_equals(db_span.data.mysql.host, "%s:3306" % mysql_host)
