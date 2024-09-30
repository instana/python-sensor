# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import sys
import MySQLdb
import pytest

from instana.singletons import agent, tracer
from tests.helpers import testenv


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="Avoiding errors with deprecated MySQL Client lib.",
)
class TestMySQLPython:
    @pytest.fixture(autouse=True)
    def _resource(self):
        self.db = MySQLdb.connect(
            host=testenv["mysql_host"],
            port=testenv["mysql_port"],
            user=testenv["mysql_user"],
            passwd=testenv["mysql_pw"],
            db=testenv["mysql_db"],
        )
        database_setup_query = """
        DROP TABLE IF EXISTS users;
        CREATE TABLE users(
            id serial primary key,
            name varchar(40) NOT NULL,
            email varchar(40) NOT NULL
        );
        INSERT INTO users(name, email) VALUES('kermit', 'kermit@muppets.com');
        DROP PROCEDURE IF EXISTS test_proc;
        CREATE PROCEDURE test_proc(IN t VARCHAR(255))
        BEGIN
            SELECT name FROM users WHERE name = t;
        END
        """
        setup_cursor = self.db.cursor()
        setup_cursor.execute(database_setup_query)
        setup_cursor.close()

        self.cursor = self.db.cursor()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        tracer.cur_ctx = None
        yield
        if self.cursor and self.cursor.connection.open:
            self.cursor.close()
        if self.db and self.db.open:
            self.db.close()
        agent.options.allow_exit_as_root = False

    def test_vanilla_query(self):
        affected_rows = self.cursor.execute("""SELECT * from users""")
        assert affected_rows == 1
        result = self.cursor.fetchone()
        assert len(result) == 3

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_basic_query(self):
        with tracer.start_as_current_span("test"):
            affected_rows = self.cursor.execute("""SELECT * from users""")
            result = self.cursor.fetchone()

        assert affected_rows == 1
        assert len(result) == 3

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from users"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_basic_query_as_root_exit_span(self):
        agent.options.allow_exit_as_root = True
        affected_rows = self.cursor.execute("""SELECT * from users""")
        result = self.cursor.fetchone()

        assert affected_rows == 1
        assert len(result) == 3

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        db_span = spans[0]

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from users"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_basic_insert(self):
        with tracer.start_as_current_span("test"):
            affected_rows = self.cursor.execute(
                """INSERT INTO users(name, email) VALUES(%s, %s)""",
                ("beaker", "beaker@muppets.com"),
            )

        assert affected_rows == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert (
            db_span.data["mysql"]["stmt"]
            == "INSERT INTO users(name, email) VALUES(%s, %s)"
        )
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_executemany(self):
        with tracer.start_as_current_span("test"):
            affected_rows = self.cursor.executemany(
                "INSERT INTO users(name, email) VALUES(%s, %s)",
                [("beaker", "beaker@muppets.com"), ("beaker", "beaker@muppets.com")],
            )
            self.db.commit()

        assert affected_rows == 2

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert (
            db_span.data["mysql"]["stmt"]
            == "INSERT INTO users(name, email) VALUES(%s, %s)"
        )
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_call_proc(self):
        with tracer.start_as_current_span("test"):
            callproc_result = self.cursor.callproc("test_proc", ("beaker",))

        assert isinstance(callproc_result, tuple)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "test_proc"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_error_capture(self):
        affected_rows = None
        try:
            with tracer.start_as_current_span("test"):
                affected_rows = self.cursor.execute("""SELECT * from blah""")
        except Exception:
            pass

        assert not affected_rows

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert db_span.ec == 2
        assert (
            db_span.data["mysql"]["error"]
            == f"(1146, \"Table '{testenv['mysql_db']}.blah' doesn't exist\")"
        )

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from blah"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_connect_cursor_ctx_mgr(self):
        with tracer.start_as_current_span("test"):
            with self.db as connection:
                with connection.cursor() as cursor:
                    affected_rows = cursor.execute("""SELECT * from users""")

        assert affected_rows == 1
        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from users"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_connect_ctx_mgr(self):
        with tracer.start_as_current_span("test"):
            with self.db as connection:
                cursor = connection.cursor()
                cursor.execute("""SELECT * from users""")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from users"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]

    def test_cursor_ctx_mgr(self):
        with tracer.start_as_current_span("test"):
            connection = self.db
            with connection.cursor() as cursor:
                affected_rows = cursor.execute("""SELECT * from users""")

        assert affected_rows == 1
        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "mysql"
        assert db_span.data["mysql"]["db"] == testenv["mysql_db"]
        assert db_span.data["mysql"]["user"] == testenv["mysql_user"]
        assert db_span.data["mysql"]["stmt"] == "SELECT * from users"
        assert db_span.data["mysql"]["host"] == testenv["mysql_host"]
        assert db_span.data["mysql"]["port"] == testenv["mysql_port"]
