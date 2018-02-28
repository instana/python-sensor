from __future__ import absolute_import

import opentracing
from nose.tools import assert_equals
from instana import internal_tracer as tracer

import redis


class TestRedis:

	# Start Redis in your .travis.yml:
	# services:
	#- redis - server

	def setUp(self):

		""" Clear all spans before a test run """
		self.redisConnection = redis.client.StrictRedis(
			host='localhost',
			port=6379,
			password='')
		self.recorder = tracer.recorder
		self.recorder.clear_spans()
		tracer.current_span = None

	def test_vanilla_getset(self):

		setvalue = self.redisConnection.set("firstName", "Stan")
		assert(setvalue)
		setvalue2 = self.redisConnection.set("lastName", "Robot")
		assert(setvalue2)

		firstName = self.redisConnection.get("firstName")
		getfirstname = firstName.decode()
		assert_equals(getfirstname, "Stan")

		lastname = self.redisConnection.get("lastName")
		getlastname = lastname.decode()
		assert_equals(getlastname, "Robot")


	def test_get_request(self):
		span = tracer.start_span("redistest")
		setfirstname  = self.redisConnection.set("firstName", "Stan")
		getfirstname  = self.redisConnection.get("firstName")
		span.finish()
		spans = self.recorder.queued_spans()


	def testredisspan(self):
		entry_span = opentracing.tracer.start_span('redis_test')
		entry_span.finish()

	def tearDown(self):
		""" Do nothing for now """
		assert_equals(None, None)
		return None