from __future__ import absolute_import
import asyncio
import instana.instrumentation
from nose.tools import assert_equals
import opentracing as ot
import psycopg2
import instana
import wrapt
import opentracing.ext.tags as ext
import time

try:

    @wrapt.patch_function_wrapper('psycopg2','connect')
    def connect_with_aiomysql(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()
        print("Instrumenting postgres psycopg2")
        try:
            span = instana.internal_tracer.start_span("postgres", child_of=context)
            span.set_tag(ext.COMPONENT, "Database")
            span.set_tag(ext.SPAN_KIND, "connect")
            rv = wrapped(*args, **kwargs)

        except Exception as e:
            span.log_kv({'message': e})
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)
            span.finish()
            raise
        else:
            span.finish()
            return rv
    instana.log.debug("Instrumenting postgres psycopg2")

except ImportError:
    pass


try:
    @wrapt.patch_function_wrapper('psycopg2.cursor','cursor.execute')
    def connect_with_aiomysql(wrapped, instance, args, kwargs):
        context = instana.internal_tracer.current_context()
        print("Instrumenting postgres psycopg2")
        try:
            span = instana.internal_tracer.start_span("postgres", child_of=context)
            span.set_tag(ext.COMPONENT, "Database")
            span.set_tag(ext.SPAN_KIND, "cursor")
            rv = wrapped(*args, **kwargs)

        except Exception as e:
            span.log_kv({'message': e})
            span.set_tag("error", True)
            ec = span.tags.get('ec', 0)
            span.set_tag("ec", ec+1)
            span.finish()
            raise
        else:
            span.finish()
            return rv
    instana.log.debug("Instrumenting postgres psycopg2")

except ImportError:
	print("No Instrumentation of psycopg2 cursor")
	pass

class TestPostgres:

	def setUp(self):
		""" Clear all spans before a test run """

		self.commands = (
			"""
			CREATE TABLE vendors (
				vendor_id SERIAL PRIMARY KEY,
				vendor_name VARCHAR(255) NOT NULL
				)
			""",
			"""DROP TABLE vendors"""
		)


		# Update connection string information obtained from the portal
		self.host = "localhost"
		self.user = "admin"
		self.dbname = "testdata"
		self.password = "##########"
		sslmode = "require"
		# Construct connection string
		self.conn_string = "host={0} user={1} dbname={2} password={3}".format(self.host, self.user, self.dbname, self.password)
		self.conn = psycopg2.connect(self.conn_string)
		self.cursor = self.conn.cursor()
		self.cursor.close()
		self.conn.commit()
		self.conn.close()

	def tearDown(self):
		""" Do nothing for now """
		return None

	def test_connection(self):
		conn = psycopg2.connect(self.conn_string)
		assert (conn is not None)
		conn.commit()
		conn.close()

	def test_cursor(self):
		conn = psycopg2.connect(self.conn_string)
		cursor = conn.cursor()
		assert (cursor is not None)
		cursor.close()
		conn.commit()
		conn.close()



	def test_query(self):
		counter = 0
		while(True):
			parent_span = ot.tracer.start_span(operation_name="postgrestest")
			parent_span.set_tag(ext.COMPONENT, "Postgres")
			parent_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
			parent_span.set_tag(ext.PEER_HOSTNAME, "localhost")
			time.sleep(3)

			for command in self.commands:
				conn = psycopg2.connect(self.conn_string)
				cursor = conn.cursor()
				cursortype = type(cursor)
				print(cursortype)
				for command in self.commands:
					cursor.execute(command)
				# close communication with the PostgreSQL database server
				cursor.close()
				conn.commit()

			parent_span.finish()
			counter = counter + 1
			if(counter > 6):
				break
		print("Ending Loop")
