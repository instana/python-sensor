from __future__ import absolute_import

import os
import sys
import json
import pytest
import unittest

from instana.tracer import InstanaTracer
from instana.options import AWSFargateOptions
from instana.recorder import AWSFargateRecorder
from instana.agent.aws_fargate import AWSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestFargate(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestFargate, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
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
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = AWSFargateAgent()
        self.span_recorder = AWSFargateRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

        # Manually set the ECS Metadata API results on the collector
        with open(self.pwd + '/../data/fargate/root_metadata.json', 'r') as json_file:
            self.agent.collector.root_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/task_metadata.json', 'r') as json_file:
            self.agent.collector.task_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/stats_metadata.json', 'r') as json_file:
            self.agent.collector.stats_metadata = json.load(json_file)
        with open(self.pwd + '/../data/fargate/task_stats_metadata.json', 'r') as json_file:
            self.agent.collector.task_stats_metadata = json.load(json_file)

    def test_prepare_payload(self):
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        assert(payload)

        assert(len(payload.keys()) == 2)
        assert('spans' in payload)
        assert(type(payload['spans']) is list)
        assert(len(payload['spans']) == 0)
        assert('metrics' in payload)
        assert(len(payload['metrics'].keys()) == 1)
        assert('plugins' in payload['metrics'])
        assert(type(payload['metrics']['plugins']) is list)
        assert(len(payload['metrics']['plugins']) == 7)

        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            assert('name' in plugin)
            assert('entityId' in plugin)
            assert('data' in plugin)

