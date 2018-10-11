from __future__ import absolute_import

import os
import sys
import unittest

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .helpers import testenv

from instana.singletons import tracer

# engine = create_engine('sqlite:///:memory:', echo=False)
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
session = Session()


class TestSQLAlchemy(unittest.TestCase):
    # def connect(self):

    def setUp(self):
        """ Clear all spans before a test run """
        self.recorder = tracer.recorder
        self.recorder.clear_spans()

    def tearDown(self):
        pass

    def test_session_add(self):
        with tracer.start_active_span('test'):
            session.add(stan_user)
            session.commit()

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
        self.assertFalse(test_span.error)
        self.assertIsNone(test_span.ec)
        self.assertFalse(sql_span.error)
        self.assertIsNone(sql_span.ec)

        # SQLAlchemy span
        self.assertEqual('sqlalchemy', sql_span.n)
        self.assertFalse('custom' in sql_span.data.__dict__)
        self.assertTrue('sqlalchemy' in sql_span.data.__dict__)

        self.assertEqual('postgresql', sql_span.data.sqlalchemy.eng)
        self.assertEqual('postgresql://tester@mazzo/rails5_stack', sql_span.data.sqlalchemy.url)
        self.assertEqual('INSERT INTO churchofstan (name, fullname, password) VALUES (%(name)s, %(fullname)s, %(password)s) RETURNING churchofstan.id', sql_span.data.sqlalchemy.sql)
        self.assertIsNone(sql_span.data.sqlalchemy.err)

        self.assertIsNotNone(sql_span.stack)
        self.assertTrue(type(sql_span.stack) is list)
        self.assertGreater(len(sql_span.stack), 0)
