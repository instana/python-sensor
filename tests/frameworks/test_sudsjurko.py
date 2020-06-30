from __future__ import absolute_import

import pytest
import unittest
import tests.apps.soap_app
from ..helpers import testenv
from suds.client import Client
from instana.singletons import tracer


@pytest.mark.skip(reason="Unstable tests")
class TestSudsJurko(unittest.TestCase):
    def setup_class(self):
        """ Clear all spans before a test run """
        self.client = Client(testenv["soap_server"] + '/?wsdl', cache=None)
        self.recorder = tracer.recorder

    def setup_method(self):
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def test_vanilla_request(self):
        response = self.client.service.ask_question(u'Why u like dat?', 5)

        self.assertEqual(1, len(response))
        self.assertEqual(1, len(response[0]))
        assert(type(response[0]) is list)

        spans = self.recorder.queued_spans()
        self.assertEqual(1, len(spans))

    def test_basic_request(self):
        with tracer.start_active_span('test'):
            response = self.client.service.ask_question(u'Why u like dat?', 5)

        spans = self.recorder.queued_spans()

        self.assertEqual(3, len(spans))
        wsgi_span = spans[0]
        soap_span = spans[1]
        test_span = spans[2]

        self.assertEqual(1, len(response))
        self.assertEqual(1, len(response[0]))
        assert(type(response[0]) is list)

        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, soap_span.t)
        self.assertEqual(soap_span.p, test_span.s)
        self.assertEqual(wsgi_span.t, soap_span.t)
        self.assertEqual(wsgi_span.p, soap_span.s)

        self.assertEqual(None, soap_span.ec)

        self.assertEqual('ask_question', soap_span.data["soap"]["action"])
        self.assertEqual(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_server_exception(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.server_exception()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        self.assertEqual(None, response)
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, soap_span.t)
        self.assertEqual(soap_span.p, test_span.s)
        self.assertEqual(wsgi_span.t, soap_span.t)
        self.assertEqual(wsgi_span.p, soap_span.s)

        self.assertEqual(1, soap_span.ec)
        self.assertEqual(u"Server raised fault: 'Internal Error'", soap_span.data["http"]["error"])
        self.assertEqual('server_exception', soap_span.data["soap"]["action"])
        self.assertEqual(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_server_fault(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.server_fault()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))
        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        self.assertEqual(None, response)
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, soap_span.t)
        self.assertEqual(soap_span.p, test_span.s)
        self.assertEqual(wsgi_span.t, soap_span.t)
        self.assertEqual(wsgi_span.p, soap_span.s)

        self.assertEqual(1, soap_span.ec)
        self.assertEqual(u"Server raised fault: 'Server side fault example.'", soap_span.data["http"]["error"])
        self.assertEqual('server_fault', soap_span.data["soap"]["action"])
        self.assertEqual(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_client_fault(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.client_fault()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        self.assertEqual(5, len(spans))

        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        self.assertEqual(None, response)
        self.assertEqual("test", test_span.data["sdk"]["name"])
        self.assertEqual(test_span.t, soap_span.t)
        self.assertEqual(soap_span.p, test_span.s)
        self.assertEqual(wsgi_span.t, soap_span.t)
        self.assertEqual(wsgi_span.p, soap_span.s)

        self.assertEqual(1, soap_span.ec)
        self.assertEqual(u"Server raised fault: 'Client side fault example'", soap_span.data["http"]["error"])
        self.assertEqual('client_fault', soap_span.data["soap"]["action"])
        self.assertEqual(testenv["soap_server"] + '/', soap_span.data["http"]["url"])
