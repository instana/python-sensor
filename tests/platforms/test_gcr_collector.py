# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from __future__ import absolute_import

import os
import json
import requests_mock
import unittest

from instana.tracer import InstanaTracer
from instana.recorder import StanRecorder
from instana.agent.google_cloud_run import GCRAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestGCRCollector(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestGCRCollector, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None
        self.pwd = os.path.dirname(os.path.realpath(__file__))

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        os.environ["PORT"] = "port"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

        if "INSTANA_ZONE" in os.environ:
            os.environ.pop("INSTANA_ZONE")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

    def tearDown(self):
        """ Reset all environment variables of consequence """
        if "PORT" in os.environ:
            os.environ.pop("PORT")
        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            os.environ.pop("INSTANA_EXTRA_HTTP_HEADERS")
        if "INSTANA_ENDPOINT_URL" in os.environ:
            os.environ.pop("INSTANA_ENDPOINT_URL")
        if "INSTANA_AGENT_KEY" in os.environ:
            os.environ.pop("INSTANA_AGENT_KEY")
        if "INSTANA_ZONE" in os.environ:
            os.environ.pop("INSTANA_ZONE")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = GCRAgent(service="service", configuration="configuration", revision="revision")
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

        # Manually set the Instance and Project Metadata API results on the collector
        with open(self.pwd + '/../data/gcr/instance_metadata.json', 'r') as json_file:
            self.agent.collector.instance_metadata = json.load(json_file)
        with open(self.pwd + '/../data/gcr/project_metadata.json', 'r') as json_file:
            self.agent.collector.project_metadata = json.load(json_file)

    @requests_mock.Mocker()
    def test_prepare_payload_basics(self, m):
        self.create_agent_and_setup_tracer()
        m.get("http://metadata.google.internal/computeMetadata/v1/project/?recursive=true",
              headers={"Metadata-Flavor": "Google"}, json=self.agent.collector.project_metadata)

        m.get("http://metadata.google.internal/computeMetadata/v1/instance/?recursive=true",
              headers={"Metadata-Flavor": "Google"}, json=self.agent.collector.instance_metadata)

        payload = self.agent.collector.prepare_payload()
        assert (payload)

        assert (len(payload.keys()) == 2)
        assert ('spans' in payload)
        assert (isinstance(payload['spans'], list))
        assert (len(payload['spans']) == 0)
        assert ('metrics' in payload)
        assert (len(payload['metrics'].keys()) == 1)
        assert ('plugins' in payload['metrics'])
        assert (isinstance(payload['metrics']['plugins'], list))
        assert (len(payload['metrics']['plugins']) == 2)

        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            # print("%s - %s" % (plugin["name"], plugin["entityId"]))
            assert ('name' in plugin)
            assert ('entityId' in plugin)
            assert ('data' in plugin)
