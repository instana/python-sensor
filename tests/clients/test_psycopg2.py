# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import logging
import pytest

from typing import Generator
from instana.instrumentation.psycopg2 import register_json_with_instana
from tests.helpers import testenv
from instana.singletons import agent, tracer

import psycopg2
import psycopg2.extras
import psycopg2.extensions as ext

logger = logging.getLogger(__name__)


class TestPsycoPG2:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        kwargs = {
            "host": testenv["postgresql_host"],
            "port": testenv["postgresql_port"],
            "user": testenv["postgresql_user"],
            "password": testenv["postgresql_pw"],
            "dbname": testenv["postgresql_db"],
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

        self.cursor = self.db.cursor()
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        tracer.cur_ctx = None
        yield
        if self.cursor and not self.cursor.connection.closed:
            self.cursor.close()
        if self.db and not self.db.closed:
            self.db.close()
        agent.options.allow_exit_as_root = False

    def test_register_json(self) -> None:
        resp = register_json_with_instana(conn_or_curs=self.db)
        assert resp[0].values[0] == 114
        assert resp[1].values[0] == 199

    def test_vanilla_query(self) -> None:
        assert psycopg2.extras.register_uuid(None, self.db)
        assert psycopg2.extras.register_uuid(None, self.db.cursor())

        self.cursor.execute("""SELECT * from users""")
        affected_rows = self.cursor.rowcount
        assert affected_rows == 1
        result = self.cursor.fetchone()

        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_basic_query(self) -> None:
        with tracer.start_as_current_span("test"):
            self.cursor.execute("""SELECT * from users""")
            affected_rows = self.cursor.rowcount
            result = self.cursor.fetchone()
            self.db.commit()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from users"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_basic_query_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.cursor.execute("""SELECT * from users""")
        affected_rows = self.cursor.rowcount
        result = self.cursor.fetchone()
        self.db.commit()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        db_span = spans[0]

        assert not db_span.ec

        assert db_span.n, "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from users"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_basic_insert(self) -> None:
        with tracer.start_as_current_span("test"):
            self.cursor.execute(
                """INSERT INTO users(name, email) VALUES(%s, %s)""",
                ("beaker", "beaker@muppets.com"),
            )
            affected_rows = self.cursor.rowcount

        assert affected_rows == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert (
            db_span.data["pg"]["stmt"]
            == "INSERT INTO users(name, email) VALUES(%s, %s)"
        )
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_executemany(self) -> None:
        with tracer.start_as_current_span("test"):
            self.cursor.executemany(
                "INSERT INTO users(name, email) VALUES(%s, %s)",
                [("beaker", "beaker@muppets.com"), ("beaker", "beaker@muppets.com")],
            )
            affected_rows = self.cursor.rowcount
            self.db.commit()

        assert affected_rows == 2

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert (
            db_span.data["pg"]["stmt"]
            == "INSERT INTO users(name, email) VALUES(%s, %s)"
        )

        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_call_proc(self) -> None:
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

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "test_proc"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_error_capture(self) -> None:
        affected_rows = result = None
        try:
            with tracer.start_as_current_span("test"):
                self.cursor.execute("""SELECT * from blah""")
                affected_rows = self.cursor.rowcount
                self.cursor.fetchone()
        except Exception:
            pass

        assert not affected_rows
        assert not result

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert db_span.ec == 2
        assert db_span.data["pg"]["error"] == (
            'relation "blah" does not exist\nLINE 1: SELECT * from blah\n                      ^\n'
        )

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from blah"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    # Added to validate unicode support and register_type.
    def test_unicode(self) -> None:
        ext.register_type(ext.UNICODE, self.cursor)
        snowman = "\u2603"

        self.cursor.execute("delete from users where id in (1,2,3)")

        # unicode in statement
        psycopg2.extras.execute_batch(
            self.cursor,
            "insert into users (id, name) values (%%s, %%s) -- %s" % snowman,
            [(1, "x")],
        )
        self.cursor.execute("select id, name from users where id = 1")
        assert self.cursor.fetchone() == (1, "x")

        # unicode in data
        psycopg2.extras.execute_batch(
            self.cursor, "insert into users (id, name) values (%s, %s)", [(2, snowman)]
        )
        self.cursor.execute("select id, name from users where id = 2")
        assert self.cursor.fetchone() == (2, snowman)

        # unicode in both
        psycopg2.extras.execute_batch(
            self.cursor,
            "insert into users (id, name) values (%%s, %%s) -- %s" % snowman,
            [(3, snowman)],
        )
        self.cursor.execute("select id, name from users where id = 3")
        assert self.cursor.fetchone() == (3, snowman)

    def test_register_type(self) -> None:
        import uuid

        oid1 = 2950
        oid2 = 2951

        ext.UUID = ext.new_type(
            (oid1,), "UUID", lambda data, cursor: data and uuid.UUID(data) or None
        )
        ext.UUIDARRAY = ext.new_array_type((oid2,), "UUID[]", ext.UUID)

        ext.register_type(ext.UUID, self.cursor)
        ext.register_type(ext.UUIDARRAY, self.cursor)

    def test_connect_cursor_ctx_mgr(self) -> None:
        with tracer.start_as_current_span("test"):
            with self.db as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""SELECT * from users""")
                    affected_rows = cursor.rowcount
                    result = cursor.fetchone()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from users"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_connect_ctx_mgr(self) -> None:
        with tracer.start_as_current_span("test"):
            with self.db as connection:
                cursor = connection.cursor()
                cursor.execute("""SELECT * from users""")
                affected_rows = cursor.rowcount
                result = cursor.fetchone()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from users"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_cursor_ctx_mgr(self) -> None:
        with tracer.start_as_current_span("test"):
            connection = self.db
            with connection.cursor() as cursor:
                cursor.execute("""SELECT * from users""")
                affected_rows = cursor.rowcount
                result = cursor.fetchone()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
        assert db_span.data["pg"]["user"] == testenv["postgresql_user"]
        assert db_span.data["pg"]["stmt"] == "SELECT * from users"
        assert db_span.data["pg"]["host"] == testenv["postgresql_host"]
        assert db_span.data["pg"]["port"] == testenv["postgresql_port"]

    def test_deprecated_parameter_database(self) -> None:
        with tracer.start_as_current_span("test"):
            self.cursor.execute("""SELECT * from users""")
            affected_rows = self.cursor.rowcount
            result = self.cursor.fetchone()
            self.db.commit()

        assert affected_rows == 1
        assert len(result) == 6

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec

        assert db_span.n == "postgres"
        assert db_span.data["pg"]["db"] == testenv["postgresql_db"]
