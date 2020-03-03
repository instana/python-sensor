from __future__ import absolute_import

from nose.tools import assert_equals
from suds.client import Client

from instana.singletons import tracer

from .helpers import testenv


class TestSudsJurko:
    def setUp(self):
        """ Clear all spans before a test run """
        self.client = Client(testenv["soap_server"] + '/?wsdl', cache=None)
        self.recorder = tracer.recorder
        self.recorder.clear_spans()
        tracer.cur_ctx = None

    def tearDown(self):
        """ Do nothing for now """
        return None

    def test_vanilla_request(self):
        response = self.client.service.ask_question(u'Why u like dat?', 5)

        assert_equals(1, len(response))
        assert_equals(1, len(response[0]))
        assert(type(response[0]) is list)

        spans = self.recorder.queued_spans()
        assert_equals(1, len(spans))

    def test_basic_request(self):
        with tracer.start_active_span('test'):
            response = self.client.service.ask_question(u'Why u like dat?', 5)

        spans = self.recorder.queued_spans()

        assert_equals(3, len(spans))
        wsgi_span = spans[0]
        soap_span = spans[1]
        test_span = spans[2]

        assert_equals(1, len(response))
        assert_equals(1, len(response[0]))
        assert(type(response[0]) is list)

        assert_equals("test", test_span.data["sdk"]["name"])
        assert_equals(test_span.t, soap_span.t)
        assert_equals(soap_span.p, test_span.s)
        assert_equals(wsgi_span.t, soap_span.t)
        assert_equals(wsgi_span.p, soap_span.s)

        assert_equals(None, soap_span.error)
        assert_equals(None, soap_span.ec)

        assert_equals('ask_question', soap_span.data["soap"]["action"])
        assert_equals(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_server_exception(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.server_exception()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert_equals(5, len(spans))

        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        assert_equals(None, response)
        assert_equals("test", test_span.data["sdk"]["name"])
        assert_equals(test_span.t, soap_span.t)
        assert_equals(soap_span.p, test_span.s)
        assert_equals(wsgi_span.t, soap_span.t)
        assert_equals(wsgi_span.p, soap_span.s)

        assert_equals(True, soap_span.error)
        assert_equals(1, soap_span.ec)
        assert('logs' in soap_span.data["custom"])
        assert_equals(1, len(soap_span.data["custom"]["logs"].keys()))

        tskey = list(soap_span.data["custom"]["logs"].keys())[0]
        assert('message' in soap_span.data["custom"]["logs"][tskey])
        assert_equals(u"Server raised fault: 'Internal Error'",
                      soap_span.data["custom"]["logs"][tskey]['message'])

        assert_equals('server_exception', soap_span.data["soap"]["action"])
        assert_equals(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_server_fault(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.server_fault()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert_equals(5, len(spans))
        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        assert_equals(None, response)
        assert_equals("test", test_span.data["sdk"]["name"])
        assert_equals(test_span.t, soap_span.t)
        assert_equals(soap_span.p, test_span.s)
        assert_equals(wsgi_span.t, soap_span.t)
        assert_equals(wsgi_span.p, soap_span.s)

        assert_equals(True, soap_span.error)
        assert_equals(1, soap_span.ec)
        assert('logs' in soap_span.data["custom"])
        assert_equals(1, len(soap_span.data["custom"]["logs"].keys()))

        tskey = list(soap_span.data["custom"]["logs"].keys())[0]
        assert('message' in soap_span.data["custom"]["logs"][tskey])
        assert_equals(u"Server raised fault: 'Server side fault example.'",
                      soap_span.data["custom"]["logs"][tskey]['message'])

        assert_equals('server_fault', soap_span.data["soap"]["action"])
        assert_equals(testenv["soap_server"] + '/', soap_span.data["http"]["url"])

    def test_client_fault(self):
        response = None
        with tracer.start_active_span('test'):
            try:
                response = self.client.service.client_fault()
            except Exception:
                pass

        spans = self.recorder.queued_spans()
        assert_equals(5, len(spans))

        log_span1 = spans[0]
        wsgi_span = spans[1]
        log_span2 = spans[2]
        soap_span = spans[3]
        test_span = spans[4]

        assert_equals(None, response)
        assert_equals("test", test_span.data["sdk"]["name"])
        assert_equals(test_span.t, soap_span.t)
        assert_equals(soap_span.p, test_span.s)
        assert_equals(wsgi_span.t, soap_span.t)
        assert_equals(wsgi_span.p, soap_span.s)

        assert_equals(True, soap_span.error)
        assert_equals(1, soap_span.ec)
        assert('logs' in soap_span.data["custom"])

        tskey = list(soap_span.data["custom"]["logs"].keys())[0]
        assert('message' in soap_span.data["custom"]["logs"][tskey])
        assert_equals(u"Server raised fault: 'Client side fault example'",
                      soap_span.data["custom"]["logs"][tskey]['message'])

        assert_equals('client_fault', soap_span.data["soap"]["action"])
        assert_equals(testenv["soap_server"] + '/', soap_span.data["http"]["url"])
