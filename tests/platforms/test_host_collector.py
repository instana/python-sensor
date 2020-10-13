from __future__ import absolute_import

import os
import json
import unittest

from instana.tracer import InstanaTracer
from instana.recorder import StanRecorder
from instana.agent.host import HostAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


class TestHostCollector(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestHostCollector, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        pass

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
        if "INSTANA_ZONE" in os.environ:
            os.environ.pop("INSTANA_ZONE")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)

    def create_agent_and_setup_tracer(self):
        self.agent = HostAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_prepare_payload_basics(self):
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        assert(payload)

        assert(len(payload.keys()) == 3)
        assert('spans' in payload)
        assert(isinstance(payload['spans'], list))
        assert(len(payload['spans']) == 0)
        assert('metrics' in payload)
        assert(len(payload['metrics'].keys()) == 1)
        assert('plugins' in payload['metrics'])
        assert(isinstance(payload['metrics']['plugins'], list))
        assert(len(payload['metrics']['plugins']) == 1)

        python_plugin = payload['metrics']['plugins'][0]
        assert python_plugin['name'] == 'com.instana.plugin.python'
        assert python_plugin['entityId'] == str(os.getpid())
        assert 'data' in python_plugin
        assert 'snapshot' in python_plugin['data']
        assert 'metrics' in python_plugin['data']

        # Validate that all metrics are reported on the first run
        assert 'ru_utime' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_utime']) in [float, int]
        assert 'ru_stime' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_stime']) in [float, int]
        assert 'ru_maxrss' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_maxrss']) in [float, int]
        assert 'ru_ixrss' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_ixrss']) in [float, int]
        assert 'ru_idrss' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_idrss']) in [float, int]
        assert 'ru_isrss' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_isrss']) in [float, int]
        assert 'ru_minflt' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_minflt']) in [float, int]
        assert 'ru_majflt' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_majflt']) in [float, int]
        assert 'ru_nswap' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_nswap']) in [float, int]
        assert 'ru_inblock' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_inblock']) in [float, int]
        assert 'ru_oublock' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_oublock']) in [float, int]
        assert 'ru_msgsnd' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_msgsnd']) in [float, int]
        assert 'ru_msgrcv' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_msgrcv']) in [float, int]
        assert 'ru_nsignals' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_nsignals']) in [float, int]
        assert 'ru_nvcsw' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_nvcsw']) in [float, int]
        assert 'ru_nivcsw' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['ru_nivcsw']) in [float, int]
        assert 'alive_threads' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['alive_threads']) in [float, int]
        assert 'dummy_threads' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['dummy_threads']) in [float, int]
        assert 'daemon_threads' in python_plugin['data']['metrics']
        assert type(python_plugin['data']['metrics']['daemon_threads']) in [float, int]
        
        assert 'gc' in python_plugin['data']['metrics']
        assert isinstance(python_plugin['data']['metrics']['gc'], dict)
        assert 'collect0' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['collect0']) in [float, int]
        assert 'collect1' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['collect1']) in [float, int]
        assert 'collect2' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['collect2']) in [float, int]
        assert 'threshold0' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['threshold0']) in [float, int]
        assert 'threshold1' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['threshold1']) in [float, int]
        assert 'threshold2' in python_plugin['data']['metrics']['gc']
        assert type(python_plugin['data']['metrics']['gc']['threshold2']) in [float, int]
