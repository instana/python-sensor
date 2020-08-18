from __future__ import absolute_import

import os
import json
import time
import logging
import urllib3
import unittest

import tests.apps.flask_app
from ..helpers import testenv, get_first_span_by_name

import instana
from instana.tracer import InstanaTracer
from instana.options import AWSFargateOptions
from instana.recorder import StanRecorder
from instana.agent.aws_fargate import AWSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestFargate(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestFargate, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
        self.http = urllib3.PoolManager()
        self.pwd = os.path.dirname(os.path.realpath(__file__))

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "AWS_EXECUTION_ENV" in os.environ:
            os.environ.pop("AWS_EXECUTION_ENV")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_ENDPOINT_PROXY" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_PROXY")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_LOG_LEVEL" in os.environ:
            os.environ.pop("INSTANA_LOG_LEVEL")
        if "INSTANA_SECRETS" in os.environ:
            os.environ.pop("INSTANA_SECRETS")
        if "INSTANA_DEBUG" in os.environ:
            os.environ.pop("INSTANA_DEBUG")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = AWSFargateAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)
        
        # Manually set the ECS Metadata API results on the collector
        with open(self.pwd + '/../data/fargate/1.3.0/root_metadata.json', 'r') as json_file:
            self.agent.collector.root_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/1.3.0/task_metadata.json', 'r') as json_file:
            self.agent.collector.task_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/1.3.0/stats_metadata.json', 'r') as json_file:
            self.agent.collector.stats_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/1.3.0/task_stats_metadata.json', 'r') as json_file:
            self.agent.collector.task_stats_metadata = json.load(json_file)


    def test_vanilla_requests(self):
        self.create_agent_and_setup_tracer()
        response = self.http.request('GET', testenv["wsgi_server"] + '/')
        spans = self.span_recorder.queued_spans()

        self.assertEqual(0, len(spans))
        self.assertIsNone(self.tracer.active_span)
        self.assertEqual(response.status, 200)

    def test_get_request(self):
        self.create_agent_and_setup_tracer()

        with self.tracer.start_active_span('test'):
            response = self.http.request('GET', testenv["wsgi_server"] + '/')
        
        spans = self.span_recorder.queued_spans()
        self.assertEqual(2, len(spans))
        self.assertIsNone(self.tracer.active_span)

        urllib3_span = get_first_span_by_name(spans, 'urllib3')
        test_span = get_first_span_by_name(spans, 'sdk')

        assert response
        self.assertEqual(200, response.status)

        assert('X-Instana-T' in response.headers)
        assert(int(response.headers['X-Instana-T'], 16))
        self.assertEqual(response.headers['X-Instana-T'], urllib3_span.t)

        assert('X-Instana-S' in response.headers)
        assert(int(response.headers['X-Instana-S'], 16))

        assert('X-Instana-L' in response.headers)
        self.assertEqual(response.headers['X-Instana-L'], '1')

        assert('Server-Timing' in response.headers)
        server_timing_value = "intid;desc=%s" % urllib3_span.t
        self.assertEqual(response.headers['Server-Timing'], server_timing_value)

        # Same traceId
        self.assertEqual(test_span.t, urllib3_span.t)

        # Parent relationships
        self.assertEqual(urllib3_span.p, test_span.s)

        self.assertIsNone(urllib3_span.sy)
        self.assertIsNone(test_span.sy)

        # Error logging
        self.assertIsNone(test_span.ec)
        self.assertIsNone(urllib3_span.ec)

        # Validate Fargate Entity Id
        assert urllib3_span.f['hl']
        assert urllib3_span.f['cp'] == 'aws'
        assert urllib3_span.f['e'] == 'arn:aws:ecs:us-east-2:410797082306:task/2d60afb1-e7fd-4761-9430-a375293a9b82::docker-ssh-aws-fargate'
