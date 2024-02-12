# (c) Copyright IBM Corp. 2024

import os
import json
import unittest

from instana.tracer import InstanaTracer
from instana.recorder import StanRecorder
from instana.agent.aws_eks_fargate import EKSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestFargateCollector(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestFargateCollector, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
        self.pwd = os.path.dirname(os.path.realpath(__file__))

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["INSTANA_TRACER_ENVIRONMENT"] = "AWS_EKS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

    def tearDown(self):
        """ Reset all environment variables of consequence """
        variable_names = (
                "INSTANA_TRACER_ENVIRONMENT",
                "AWS_EXECUTION_ENV", "INSTANA_EXTRA_HTTP_HEADERS",
                "INSTANA_ENDPOINT_URL", "INSTANA_ENDPOINT_PROXY",
                "INSTANA_AGENT_KEY", "INSTANA_ZONE", "INSTANA_TAGS"
                )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = EKSFargateAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_prepare_payload_basics(self):
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)

        self.assertEqual(2, len(payload.keys()))
        self.assertIn('spans',payload)
        self.assertIsInstance(payload['spans'], list)
        self.assertEqual(0, len(payload['spans']))
        self.assertIn('metrics', payload)
        self.assertEqual(1, len(payload['metrics'].keys()))
        self.assertIn('plugins', payload['metrics'])
        self.assertIsInstance(payload['metrics']['plugins'], list)
        self.assertEqual(2, len(payload['metrics']['plugins']))


        process_plugin = payload['metrics']['plugins'][0]
        #self.assertIn('data', process_plugin)

        runtime_plugin = payload['metrics']['plugins'][1]
        self.assertIn('name', runtime_plugin)
        self.assertIn('entityId', runtime_plugin)
        self.assertIn('data', runtime_plugin)

    def test_no_instana_zone(self):
        self.create_agent_and_setup_tracer()
        self.assertIsNone(self.agent.options.zone)

