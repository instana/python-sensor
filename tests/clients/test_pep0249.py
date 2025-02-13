import logging
from typing import Generator
from unittest.mock import patch

import psycopg2
import psycopg2.extras
import pytest
from instana.instrumentation.pep0249 import (
    ConnectionFactory,
    ConnectionWrapper,
    CursorWrapper,
)
from instana.singletons import tracer
from instana.span.span import InstanaSpan
from opentelemetry.trace import SpanKind
from pytest import LogCaptureFixture

from tests.helpers import testenv


class TestCursorWrapper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.connect_params = [
            "db",
            {
                "db": testenv["postgresql_db"],
                "host": testenv["postgresql_host"],
                "port": testenv["postgresql_port"],
                "user": testenv["postgresql_user"],
                "password": testenv["postgresql_pw"],
            },
        ]
        self.test_conn = psycopg2.connect(
            database=self.connect_params[1]["db"],
            host=self.connect_params[1]["host"],
            port=self.connect_params[1]["port"],
            user=self.connect_params[1]["user"],
            password=self.connect_params[1]["password"],
        )
        self.cursor_params = {"key": "value"}
        self.test_cursor = self.test_conn.cursor()
        self.cursor_name = "test-cursor"
        self.test_wrapper = CursorWrapper(
            self.test_cursor,
            self.cursor_name,
            self.connect_params,
            self.cursor_params,
        )
        yield
        self.test_cursor.close()
        self.test_conn.close()

    def reset_table(self) -> None:
        self.test_cursor.execute(
            """
            DROP TABLE IF EXISTS tests;
            CREATE TABLE tests (id SERIAL PRIMARY KEY, name VARCHAR(50), email VARCHAR(100));
            """
        )
        self.test_cursor.execute(
            """
            INSERT INTO tests (id, name, email) VALUES (1, 'test-name', 'testemail@mail.com');
            """
        )
        self.test_conn.commit()

    def reset_procedure(self) -> None:
        self.test_cursor.execute("""
            DROP PROCEDURE IF EXISTS insert_user(IN test_id INT, IN test_name VARCHAR, IN test_email VARCHAR);
            CREATE PROCEDURE insert_user(IN test_id INT, IN test_name VARCHAR, IN test_email VARCHAR)
            LANGUAGE plpgsql
            AS $$
            BEGIN
                INSERT INTO tests (id, name, email) VALUES (test_id, test_name, test_email);
            END;
            $$;
            """)
        self.test_conn.commit()

    def test_cursor_wrapper_default(self) -> None:
        # CursorWrapper
        assert self.test_wrapper
        assert self.test_wrapper._module_name == self.cursor_name
        connection_params = {"db", "host", "port", "user", "password"}
        assert connection_params.issubset(self.test_wrapper._connect_params[1].keys())
        assert not self.test_wrapper.closed
        assert self.test_wrapper._cursor_params == self.cursor_params

        # Test Connection
        assert (
            self.test_conn.dsn
            == "user=root password=xxx dbname=instana_test_db host=127.0.0.1 port=5432"
        )
        assert not self.test_conn.autocommit
        assert self.test_conn.status == 1
        assert self.test_conn.info.dbname == "instana_test_db"
        assert self.test_conn.info.host == "127.0.0.1"
        assert self.test_conn.info.user == "root"
        assert self.test_conn.info.port == 5432

        # Test Cursor
        assert self.test_cursor.arraysize == 1
        assert isinstance(self.test_cursor, psycopg2.extensions.cursor)
        assert hasattr(self.test_cursor, "callproc")
        assert hasattr(self.test_cursor, "close")
        assert hasattr(self.test_cursor, "execute")
        assert hasattr(self.test_cursor, "executemany")
        assert hasattr(self.test_cursor, "fetchone")
        assert hasattr(self.test_cursor, "fetchall")

    def test_collect_kvs(self) -> None:
        self.reset_table()
        with tracer.start_as_current_span("test") as span:
            sample_sql = """
                select * from tests;
            """
            self.test_wrapper._collect_kvs(span, sample_sql)
            assert span.attributes["db.name"] == "instana_test_db"
            assert span.attributes["db.statement"] == sample_sql
            assert span.attributes["db.user"] == "root"
            assert span.attributes["host"] == "127.0.0.1"
            assert span.attributes["port"] == 5432

    def test_collect_kvs_error(self, caplog: LogCaptureFixture) -> None:
        self.reset_table()
        with tracer.start_as_current_span("test") as span:
            connect_params = "sample"
            sample_wrapper = CursorWrapper(
                self.test_cursor,
                self.cursor_name,
                connect_params,
            )
            sample_sql = "select * from tests;"
            caplog.set_level(logging.DEBUG, logger="instana")
            sample_wrapper._collect_kvs(span, sample_sql)
            assert "string indices must be integers" in caplog.messages[0]

    def test_enter(self) -> None:
        response = self.test_wrapper.__enter__()
        assert response == self.test_wrapper
        assert isinstance(response, CursorWrapper)

    def test_execute_with_tracing_off(self) -> None:
        self.reset_table()
        with tracer.start_as_current_span("sqlalchemy"):
            sample_sql = """insert into tests (id, name, email) values (%s, %s, %s) returning id, name, email;"""
            sample_params = (2, "sample-name", "sample-email@mail.com")
            self.test_wrapper.execute(sample_sql, sample_params)
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            assert sample_params in response
            assert len(response) == 2

    def test_execute_with_tracing(self) -> None:
        self.reset_table()
        with tracer.start_as_current_span("test"):
            sample_sql = """insert into tests (id, name, email) values (%s, %s, %s) returning id, name, email;"""
            sample_params = (3, "sample-name", "sample-email@mail.com")
            self.test_wrapper.execute(sample_sql, sample_params)
            last_inserted_row = self.test_cursor.fetchone()
            self.test_conn.commit()
            assert last_inserted_row == sample_params

            # Exception Handling
            with pytest.raises(Exception) as exc_info, patch.object(
                CursorWrapper, "_collect_kvs", side_effect=Exception("test exception")
            ) as mock_collect_kvs:
                self.test_wrapper.execute(sample_sql)
            assert str(exc_info.value) == "test exception"
            mock_collect_kvs.assert_called_once()
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            assert sample_params in response
            assert len(response) == 2

    def test_executemany_with_tracing_off(self) -> None:
        self.reset_table()
        with tracer.start_as_current_span("sqlalchemy"):
            sample_sql = """insert into tests (id, name, email) values (%s, %s, %s) returning id, name, email;"""
            sample_seq_of_params = [
                (4, "sample-name-3", "sample-email-3@mail.com"),
                (5, "sample-name-4", "sample-email-4@mail.com"),
            ]
            self.test_wrapper.executemany(sample_sql, sample_seq_of_params)
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            for record in sample_seq_of_params:
                assert record in response
            assert len(response) == 3

    def test_executemany_with_tracing(self) -> None:
        self.reset_table()
        with tracer.start_as_current_span("test"):
            sample_sql = """insert into tests (id, name, email) values (%s, %s, %s) returning id, name, email;"""
            sample_seq_of_params = [
                (6, "sample-name-3", "sample-email-3@mail.com"),
                (7, "sample-name-4", "sample-email-4@mail.com"),
            ]
            self.test_wrapper.executemany(sample_sql, sample_seq_of_params)

            # Exception Handling
            with pytest.raises(Exception) as exc_info, patch.object(
                CursorWrapper, "_collect_kvs", side_effect=Exception("test exception")
            ) as mock_collect_kvs:
                self.test_wrapper.executemany(
                    sample_sql, seq_of_parameters=sample_seq_of_params
                )
            assert str(exc_info.value) == "test exception"
            mock_collect_kvs.assert_called_once()
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            for record in sample_seq_of_params:
                assert record in response
            assert len(response) == 3

    def test_callproc_with_tracing_off(self) -> None:
        self.reset_table()
        self.reset_procedure()
        with tracer.start_as_current_span("sqlalchemy"):
            sample_proc_name = "call insert_user(%s, %s, %s);"
            sample_params = (8, "sample-name-8", "sample-email-8@mail.com")
            self.test_wrapper.callproc(sample_proc_name, sample_params)
            self.test_conn.commit()
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            assert sample_params in response
            assert len(response) == 2

    def test_callproc_with_tracing(self) -> None:
        self.reset_table()
        self.reset_procedure()
        with tracer.start_as_current_span("test"):
            sample_proc_name = "call insert_user(%s, %s, %s);"
            sample_params = (9, "sample-name-9", "sample-email-9@mail.com")
            self.test_wrapper.callproc(sample_proc_name, sample_params)
            self.test_conn.commit()
            self.test_wrapper.execute("select * from tests;")
            response = self.test_wrapper.fetchall()
            assert sample_params in response
            assert len(response) == 2

            # Exception Handling
            error_proc_name = "erroroeus command;"
            with pytest.raises(Exception) as exc_info, patch.object(
                InstanaSpan,
                "record_exception",
            ) as mock_exception:
                self.test_wrapper.callproc(error_proc_name, sample_params)
            assert exc_info.typename == "SyntaxError"
            mock_exception.call_count == 2


class TestConnectionWrapper:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.connect_params = [
            "db",
            {
                "db": "instana_test_db",
                "host": "localhost",
                "port": "5432",
                "user": "root",
                "password": "passw0rd",
            },
        ]
        self.test_conn = psycopg2.connect(
            database=self.connect_params[1]["db"],
            host=self.connect_params[1]["host"],
            port=self.connect_params[1]["port"],
            user=self.connect_params[1]["user"],
            password=self.connect_params[1]["password"],
        )
        self.module_name = "test-connection"
        self.connection_manager = ConnectionWrapper(
            self.test_conn, self.module_name, self.connect_params
        )
        yield
        self.test_conn.close()

    def test_enter(self) -> None:
        response = self.connection_manager.__enter__()
        assert isinstance(response, ConnectionWrapper)
        assert response._module_name == self.module_name
        assert response._connect_params == self.connect_params

    def test_cursor(self) -> None:
        response = self.connection_manager.cursor()
        assert isinstance(response, CursorWrapper)

    def test_close(self) -> None:
        response = self.connection_manager.close()
        assert self.test_conn.closed
        assert not response

    def test_commit(self) -> None:
        response = self.connection_manager.commit()
        assert not response

    def test_rollback(self) -> None:
        if hasattr(self.connection_manager, "rollback"):
            response = self.connection_manager.rollback()
            assert not response


class TestConnectionFactory:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.test_conn_func = psycopg2.connect
        self.test_module_name = "test-factory"
        self.conn_fact = ConnectionFactory(self.test_conn_func, self.test_module_name)
        yield
        self.test_conn_func = None
        self.test_module_name = None
        self.conn_fact = None

    def test_call(self) -> None:
        response = self.conn_fact(
            dsn="user=root password=passw0rd dbname=instana_test_db host=localhost port=5432"
        )
        assert isinstance(self.conn_fact._wrapper_ctor, ConnectionWrapper.__class__)
        assert self.conn_fact._connect_func == self.test_conn_func
        assert self.conn_fact._module_name == self.test_module_name
        assert isinstance(response, ConnectionWrapper)
