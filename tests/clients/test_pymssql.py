# (c) Copyright IBM Corp. 2026

from typing import Generator

import pytest

from instana.singletons import agent, get_tracer
from tests.helpers import testenv


class TestPyMSSQL:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        import pymssql

        try:
            self.db = pymssql.connect(
                server=testenv["mssql_host"],
                port=testenv["mssql_port"],
                user=testenv["mssql_user"],
                password=testenv["mssql_pw"],
                database=testenv["mssql_db"],
            )
        except Exception:
            pytest.skip("SQL Server not available")

        setup_cursor = self.db.cursor()
        setup_cursor.execute("IF OBJECT_ID('users', 'U') IS NOT NULL DROP TABLE users")
        setup_cursor.execute(
            "CREATE TABLE users (id INT, name NVARCHAR(50), email NVARCHAR(50))"
        )
        setup_cursor.execute(
            "INSERT INTO users (id, name, email) VALUES (1, 'kermit', 'kermit@muppets.com')"
        )
        self.db.commit()

        self.cursor = self.db.cursor()
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        self.tracer.cur_ctx = None
        yield
        try:
            cleanup_cursor = self.db.cursor()
            cleanup_cursor.execute(
                "IF OBJECT_ID('users', 'U') IS NOT NULL DROP TABLE users"
            )
            self.db.commit()
            self.cursor.close()
            self.db.close()
        except Exception:
            pass
        agent.options.allow_exit_as_root = False

    # ------------------------------------------------------------------ US1 --

    def test_vanilla_query(self) -> None:
        """No tracer context → zero spans emitted."""
        self.cursor.execute("SELECT * FROM users")
        rows = self.cursor.fetchall()
        assert len(rows) == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_basic_query(self) -> None:
        """SELECT inside tracer context → one mssql child span with all attributes."""
        with self.tracer.start_as_current_span("test"):
            self.cursor.execute("SELECT * FROM users")
            rows = self.cursor.fetchall()

        assert len(rows) == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span, test_span = spans

        assert test_span.data["sdk"]["name"] == "test"
        assert test_span.t == db_span.t
        assert db_span.p == test_span.s

        assert not db_span.ec
        assert db_span.n == "mssql"
        assert db_span.data["mssql"]["db"] == testenv["mssql_db"]
        assert db_span.data["mssql"]["user"] == testenv["mssql_user"]
        assert db_span.data["mssql"]["stmt"] == "SELECT * FROM users"
        assert db_span.data["mssql"]["host"] == testenv["mssql_host"]
        assert db_span.data["mssql"]["port"] == testenv["mssql_port"]

    def test_basic_query_as_root_exit_span(self) -> None:
        """Root exit span (no parent) is captured when allow_exit_as_root is True."""
        agent.options.allow_exit_as_root = True
        self.cursor.execute("SELECT * FROM users")
        rows = self.cursor.fetchall()

        assert len(rows) == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        db_span = spans[0]

        assert not db_span.ec
        assert db_span.n == "mssql"
        assert db_span.data["mssql"]["db"] == testenv["mssql_db"]
        assert db_span.data["mssql"]["user"] == testenv["mssql_user"]
        assert db_span.data["mssql"]["stmt"] == "SELECT * FROM users"
        assert db_span.data["mssql"]["host"] == testenv["mssql_host"]
        assert db_span.data["mssql"]["port"] == testenv["mssql_port"]

    @pytest.mark.parametrize(
        "sql,expected_stmt",
        [
            (
                "SELECT * FROM users WHERE id = 1",
                "SELECT * FROM users WHERE id = ?",
            ),
            (
                "INSERT INTO users (id, name, email) VALUES (2, 'beaker', 'beaker@muppets.com')",
                "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
            ),
            (
                "UPDATE users SET name = 'gonzo' WHERE id = 1",
                "UPDATE users SET name = ? WHERE id = ?",
            ),
        ],
    )
    def test_span_attributes(self, sql: str, expected_stmt: str) -> None:
        """All five non-error span attributes are populated for each DML statement."""
        with self.tracer.start_as_current_span("test"):
            try:
                self.cursor.execute(sql)
                self.db.commit()
            except Exception:
                self.db.rollback()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        db_span = spans[0]

        assert db_span.n == "mssql"
        assert db_span.data["mssql"]["db"] == testenv["mssql_db"]
        assert db_span.data["mssql"]["user"] == testenv["mssql_user"]
        assert db_span.data["mssql"]["stmt"] == expected_stmt
        assert db_span.data["mssql"]["host"] == testenv["mssql_host"]
        assert db_span.data["mssql"]["port"] == testenv["mssql_port"]
        assert not db_span.ec

    def test_connect_cursor_ctx_mgr(self) -> None:
        """Cursor used as a context manager produces the same span output."""
        with self.tracer.start_as_current_span("test"), self.cursor:
            self.cursor.execute("SELECT * FROM users")
            rows = self.cursor.fetchall()

        assert len(rows) == 1

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        db_span = spans[0]

        assert db_span.n == "mssql"
        assert db_span.data["mssql"]["stmt"] == "SELECT * FROM users"
        assert not db_span.ec

    # ------------------------------------------------------------------ US2 --

    @pytest.mark.parametrize(
        "bad_sql",
        [
            "SELECT * FROM nonexistent_table_xyz",
            "THIS IS NOT VALID SQL AT ALL",
        ],
    )
    def test_error_capture(self, bad_sql: str) -> None:
        """Failed queries record ec=1 and populate the error attribute."""
        with self.tracer.start_as_current_span("test"), pytest.raises(Exception):
            self.cursor.execute(bad_sql)

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        db_span = spans[0]

        assert db_span.n == "mssql"
        assert db_span.ec == 2
        assert db_span.data["mssql"]["error"] is not None
        assert len(db_span.data["mssql"]["error"]) > 0

    def test_no_error_on_success(self) -> None:
        """Successful queries leave ec falsy and error attribute as None."""
        with self.tracer.start_as_current_span("test"):
            self.cursor.execute("SELECT * FROM users")

        spans = self.recorder.queued_spans()
        assert len(spans) == 2
        db_span = spans[0]

        assert db_span.n == "mssql"
        assert not db_span.ec
        assert db_span.data["mssql"]["error"] is None

    # ------------------------------------------------------------------ US3 --

    @pytest.mark.parametrize(
        "batch_rows",
        [
            [(2, "beaker", "beaker@muppets.com"), (3, "fozzie", "fozzie@muppets.com")],
            [
                (2, "beaker", "b@m.com"),
                (3, "fozzie", "f@m.com"),
                (4, "gonzo", "g@m.com"),
                (5, "piggy", "p@m.com"),
                (6, "animal", "a@m.com"),
            ],
        ],
    )
    def test_executemany(self, batch_rows: list) -> None:
        """executemany produces exactly one mssql span regardless of batch size."""
        sql = "INSERT INTO users (id, name, email) VALUES (%d, %s, %s)"
        with self.tracer.start_as_current_span("test"):
            self.cursor.executemany(sql, batch_rows)
            self.db.commit()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        db_span = spans[0]
        assert db_span.n == "mssql"
        assert db_span.data["mssql"]["stmt"] is not None
        assert not db_span.ec

    # --------------------------------------------------------------- Polish --

    def test_sqlalchemy_bypass(self) -> None:
        """When the active span is 'sqlalchemy', no mssql span is created."""
        with self.tracer.start_as_current_span("sqlalchemy"):
            self.cursor.execute("SELECT * FROM users")

        spans = self.recorder.queued_spans()
        # Only the sqlalchemy span; no mssql child
        assert len(spans) == 1
        assert spans[0].n == "sqlalchemy"
