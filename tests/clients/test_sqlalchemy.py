# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from typing import Generator

import pytest
from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from tests.helpers import testenv

engine = create_engine(
    f"postgresql://{testenv['postgresql_user']}:{testenv['postgresql_pw']}@{testenv['postgresql_host']}:{testenv['postgresql_port']}/{testenv['postgresql_db']}"
)

Session = sessionmaker(bind=engine)
Base = declarative_base()


class StanUser(Base):
    __tablename__ = "churchofstan"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True)
    name = Column(String)
    fullname = Column(String)
    password = Column(String)

    def __repr__(self) -> None:
        return "<User(name='%s', fullname='%s', password='%s')>" % (
            self.name,
            self.fullname,
            self.password,
        )


@pytest.fixture(scope="class")
def db_setup() -> None:
    with tracer.start_as_current_span("metadata") as span:
        Base.metadata.create_all(engine)
        span.end()


stan_user = StanUser(
    name="IAmStan",
    fullname="Stan Robot",
    password="3X}vP66ADoCFT2g?HPvoem2eJh,zWXgd36Rb/{aRq/>7EYy6@EEH4BP(oeXac@mR",
)
stan_user2 = StanUser(
    name="IAmStanToo",
    fullname="Stan Robot 2",
    password="3X}vP66ADoCFT2g?HPvoem2eJh,zWXgd36Rb/{aRq/>7EYy6@EEH4BP(oeXac@mR",
)

sqlalchemy_url = f"postgresql://{testenv['postgresql_host']}:{testenv['postgresql_port']}/{testenv['postgresql_db']}"


@pytest.mark.usefixtures("db_setup")
class TestSQLAlchemy:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.session = Session()
        yield
        """Ensure that allow_exit_as_root has the default value"""
        self.session.close()
        agent.options.allow_exit_as_root = False

    def test_session_add(self) -> None:
        with tracer.start_as_current_span("test"):
            self.session.add(stan_user)
            self.session.commit()

        spans = self.recorder.queued_spans()

        sql_span = spans[0]
        test_span = spans[1]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert sql_span.t == test_span.t

        # Parent relationships
        assert sql_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not sql_span.ec

        # SQLAlchemy span
        assert sql_span.n == "sqlalchemy"
        assert "custom" not in sql_span.data
        assert "sqlalchemy" in sql_span.data

        assert sql_span.data["sqlalchemy"]["eng"] == "postgresql"
        assert sqlalchemy_url == sql_span.data["sqlalchemy"]["url"]
        assert (
            "INSERT INTO churchofstan (name, fullname, password) VALUES (%(name)s, %(fullname)s, %(password)s) RETURNING churchofstan.id"
            == sql_span.data["sqlalchemy"]["sql"]
        )
        assert not sql_span.data["sqlalchemy"]["err"]

        assert sql_span.stack
        assert isinstance(sql_span.stack, list)
        assert len(sql_span.stack) > 0

    def test_session_add_as_root_exit_span(self) -> None:
        agent.options.allow_exit_as_root = True
        self.session.add(stan_user2)
        self.session.commit()

        spans = self.recorder.queued_spans()
        assert len(spans) == 1

        sql_span = spans[0]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Parent relationships
        assert not sql_span.p

        # Error logging
        assert not sql_span.ec

        # SQLAlchemy span
        assert sql_span.n == "sqlalchemy"
        assert "custom" not in sql_span.data
        assert "sqlalchemy" in sql_span.data

        assert sql_span.data["sqlalchemy"]["eng"] == "postgresql"
        assert sqlalchemy_url == sql_span.data["sqlalchemy"]["url"]
        assert (
            "INSERT INTO churchofstan (name, fullname, password) VALUES (%(name)s, %(fullname)s, %(password)s) RETURNING churchofstan.id"
            == sql_span.data["sqlalchemy"]["sql"]
        )
        assert not sql_span.data["sqlalchemy"]["err"]

        assert sql_span.stack
        assert isinstance(sql_span.stack, list)
        assert len(sql_span.stack) > 0

    def test_transaction(self) -> None:
        with tracer.start_as_current_span("test"):
            with engine.begin() as connection:
                connection.execute(text("select 1"))
                connection.execute(
                    text(
                        "select (name, fullname, password) from churchofstan where name='doesntexist'"
                    )
                )

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        sql_span0 = spans[0]
        sql_span1 = spans[1]
        test_span = spans[2]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert sql_span0.t == test_span.t
        assert sql_span1.t == test_span.t

        # Parent relationships
        assert sql_span0.p == test_span.s
        assert sql_span1.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not sql_span0.ec
        assert not sql_span1.ec

        # SQLAlchemy span0
        assert sql_span0.n == "sqlalchemy"
        assert "custom" not in sql_span0.data
        assert "sqlalchemy" in sql_span0.data

        assert sql_span0.data["sqlalchemy"]["eng"] == "postgresql"
        assert sqlalchemy_url == sql_span0.data["sqlalchemy"]["url"]
        assert sql_span0.data["sqlalchemy"]["sql"] == "select 1"
        assert not sql_span0.data["sqlalchemy"]["err"]

        assert sql_span0.stack
        assert isinstance(sql_span0.stack, list)
        assert len(sql_span0.stack) > 0

        # SQLAlchemy span1
        assert sql_span1.n == "sqlalchemy"
        assert "custom" not in sql_span1.data
        assert "sqlalchemy" in sql_span1.data

        assert sql_span1.data["sqlalchemy"]["eng"] == "postgresql"
        assert sqlalchemy_url == sql_span1.data["sqlalchemy"]["url"]
        assert (
            "select (name, fullname, password) from churchofstan where name='doesntexist'"
            == sql_span1.data["sqlalchemy"]["sql"]
        )
        assert not sql_span1.data["sqlalchemy"]["err"]

        assert sql_span1.stack
        assert isinstance(sql_span1.stack, list)
        assert len(sql_span1.stack) > 0

    def test_error_logging(self) -> None:
        with tracer.start_as_current_span("test"):
            try:
                self.session.execute(text("htVwGrCwVThisIsInvalidSQLaw4ijXd88"))
                # self.session.commit()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        sql_span = spans[0]
        test_span = spans[1]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert sql_span.t == test_span.t

        # Parent relationships
        assert sql_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert sql_span.ec == 1

        # SQLAlchemy span
        assert sql_span.n == "sqlalchemy"

        assert "custom" not in sql_span.data
        assert "sqlalchemy" in sql_span.data

        assert sql_span.data["sqlalchemy"]["eng"] == "postgresql"
        assert sqlalchemy_url == sql_span.data["sqlalchemy"]["url"]
        assert (
            "htVwGrCwVThisIsInvalidSQLaw4ijXd88" == sql_span.data["sqlalchemy"]["sql"]
        )
        assert (
            'syntax error at or near "htVwGrCwVThisIsInvalidSQLaw4ijXd88'
            in sql_span.data["sqlalchemy"]["err"]
        )
        assert sql_span.stack
        assert isinstance(sql_span.stack, list)
        assert len(sql_span.stack) > 0

    def test_error_before_tracing(self) -> None:
        """Test the scenario, in which instana is loaded,
        but connection fails before tracing begins.
        This is typical in test container scenario,
        where it is "normal" to just start hammering a database container
        which is still starting and not ready to handle requests yet.
        In this scenario it is important that we get
        an sqlalachemy exception, and not something else
        like an AttributeError. Because testcontainer has a logic
        to retry in case of certain sqlalchemy exceptions but it
        can't handle an AttributeError."""
        # https://github.com/instana/python-sensor/issues/362

        current_span = get_current_span()
        assert not current_span.is_recording()

        invalid_connection_url = "postgresql://user1:pwd1@localhost:9999/mydb1"
        with pytest.raises(
            OperationalError,
            match=r"^(\(psycopg2\.OperationalError\)).*",
        ) as context_manager:
            engine = create_engine(invalid_connection_url)
            with engine.connect() as connection:
                (version,) = connection.execute(text("select version()")).fetchone()

        the_exception = context_manager.value
        assert not the_exception.connection_invalidated

    def test_if_not_tracing(self) -> None:
        with engine.begin() as connection:
            connection.execute(text("select 1"))
            connection.execute(
                text(
                    "select (name, fullname, password) from churchofstan where name='doesntexist'"
                )
            )

        current_span = get_current_span()
        assert not current_span.is_recording()
