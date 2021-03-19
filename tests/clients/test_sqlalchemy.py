# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

from __future__ import absolute_import

import unittest

from ..helpers import testenv
from instana.singletons import tracer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, create_engine


engine = create_engine("postgresql://%s:%s@%s/%s" % (testenv['postgresql_user'], testenv['postgresql_pw'],
                                                     testenv['postgresql_host'], testenv['postgresql_db']))
Base = declarative_base()

class StanUser(Base):
     __tablename__ = 'churchofstan'

     id = Column(Integer, primary_key=True)
     name = Column(String)
     fullname = Column(String)
     password = Column(String)

     def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
                             self.name, self.fullname, self.password)

Base.metadata.create_all(engine)

stan_user = StanUser(name='IAmStan', fullname='Stan Robot', password='3X}vP66ADoCFT2g?HPvoem2eJh,zWXgd36Rb/{aRq/>7EYy6@EEH4BP(oeXac@mR')

Session = sessionmaker(bind=engine)
Session.configure(bind=engine)

sqlalchemy_url = 'postgresql://%s/%s' % (testenv['postgresql_host'], testenv['postgresql_db'])


class TestSQLAlchemy(unittest.TestCase):
    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        self.session = Session()

    def tearDown(self):
        pass

    def test_session_add(self):
        with tracer.start_active_span('test'):
            self.session.add(stan_user)
            self.session.commit()

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        sql_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, sql_span.t)

        # Parent relationships
        self.assertEqual(sql_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(sql_span.ec)

        # SQLAlchemy span
        self.assertEqual('sqlalchemy', sql_span.n)
        self.assertFalse('custom' in sql_span.data)
        self.assertTrue('sqlalchemy' in sql_span.data)

        self.assertEqual('postgresql', sql_span.data["sqlalchemy"]["eng"])
        self.assertEqual(sqlalchemy_url, sql_span.data["sqlalchemy"]["url"])
        self.assertEqual('INSERT INTO churchofstan (name, fullname, password) VALUES (%(name)s, %(fullname)s, %(password)s) RETURNING churchofstan.id', sql_span.data["sqlalchemy"]["sql"])
        self.assertIsNone(sql_span.data["sqlalchemy"]["err"])

        self.assertIsNotNone(sql_span.stack)
        self.assertTrue(type(sql_span.stack) is list)
        self.assertGreater(len(sql_span.stack), 0)

    def test_transaction(self):
        result = None
        with tracer.start_active_span('test'):
            with engine.begin() as connection:
                result = connection.execute("select 1")
                result = connection.execute("select (name, fullname, password) from churchofstan where name='doesntexist'")

        spans = self.recorder.queued_spans()
        self.assertEqual(3, len(spans))

        sql_span0 = spans[0]
        sql_span1 = spans[1]
        test_span = spans[2]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, sql_span0.t)
        self.assertEqual(test_span.t, sql_span1.t)

        # Parent relationships
        self.assertEqual(sql_span0.p, test_span.s)
        self.assertEqual(sql_span1.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(sql_span0.ec)
        self.assertIsNone(sql_span1.ec)

        # SQLAlchemy span0
        self.assertEqual('sqlalchemy', sql_span0.n)
        self.assertFalse('custom' in sql_span0.data)
        self.assertTrue('sqlalchemy' in sql_span0.data)

        self.assertEqual('postgresql', sql_span0.data["sqlalchemy"]["eng"])
        self.assertEqual(sqlalchemy_url, sql_span0.data["sqlalchemy"]["url"])
        self.assertEqual('select 1', sql_span0.data["sqlalchemy"]["sql"])
        self.assertIsNone(sql_span0.data["sqlalchemy"]["err"])

        self.assertIsNotNone(sql_span0.stack)
        self.assertTrue(type(sql_span0.stack) is list)
        self.assertGreater(len(sql_span0.stack), 0)

        # SQLAlchemy span1
        self.assertEqual('sqlalchemy', sql_span1.n)
        self.assertFalse('custom' in sql_span1.data)
        self.assertTrue('sqlalchemy' in sql_span1.data)

        self.assertEqual('postgresql', sql_span1.data["sqlalchemy"]["eng"])
        self.assertEqual(sqlalchemy_url, sql_span1.data["sqlalchemy"]["url"])
        self.assertEqual("select (name, fullname, password) from churchofstan where name='doesntexist'", sql_span1.data["sqlalchemy"]["sql"])
        self.assertIsNone(sql_span1.data["sqlalchemy"]["err"])

        self.assertIsNotNone(sql_span1.stack)
        self.assertTrue(type(sql_span1.stack) is list)
        self.assertGreater(len(sql_span1.stack), 0)

    def test_error_logging(self):
        with tracer.start_active_span('test'):
            try:
                self.session.execute("htVwGrCwVThisIsInvalidSQLaw4ijXd88")
                self.session.commit()
            except:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(2, len(spans))

        sql_span = spans[0]
        test_span = spans[1]

        self.assertIsNone(tracer.active_span)

        # Same traceId
        self.assertEqual(test_span.t, sql_span.t)

        # Parent relationships
        self.assertEqual(sql_span.p, test_span.s)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIs(sql_span.ec, 1)

        # SQLAlchemy span
        self.assertEqual('sqlalchemy', sql_span.n)

        self.assertFalse('custom' in sql_span.data)
        self.assertTrue('sqlalchemy' in sql_span.data)

        self.assertEqual('postgresql', sql_span.data["sqlalchemy"]["eng"])
        self.assertEqual(sqlalchemy_url, sql_span.data["sqlalchemy"]["url"])
        self.assertEqual('htVwGrCwVThisIsInvalidSQLaw4ijXd88', sql_span.data["sqlalchemy"]["sql"])
        self.assertIn('syntax error at or near "htVwGrCwVThisIsInvalidSQLaw4ijXd88', sql_span.data["sqlalchemy"]["err"])
        self.assertIsNotNone(sql_span.stack)
        self.assertTrue(type(sql_span.stack) is list)
        self.assertGreater(len(sql_span.stack), 0)
