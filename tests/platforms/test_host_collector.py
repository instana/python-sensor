# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import unittest
import sys

from mock import patch

from instana.tracer import InstanaTracer
from instana.recorder import StanRecorder
from instana.agent.host import HostAgent
from instana.collector.helpers.runtime import PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR
from instana.collector.host import HostCollector
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer
from instana.version import VERSION

class TestHostCollector(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        super(TestHostCollector, self).__init__(methodName)
        self.agent = None
        self.span_recorder = None
        self.tracer = None

        self.original_agent = get_agent()
        self.original_tracer = get_tracer()

    def setUp(self):
        self.webhook_sitedir_path = PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR + '3.8.0'

    def tearDown(self):
        """ Reset all environment variables of consequence """
        variable_names = (
                "AWS_EXECUTION_ENV", "INSTANA_EXTRA_HTTP_HEADERS",
                "INSTANA_ENDPOINT_URL", "INSTANA_AGENT_KEY", "INSTANA_ZONE",
                "INSTANA_TAGS", "INSTANA_DISABLE_METRICS_COLLECTION",
                "INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION",
                "AUTOWRAPT_BOOTSTRAP"
                )

        for variable_name in variable_names:
            if variable_name in os.environ:
                os.environ.pop(variable_name)

        set_agent(self.original_agent)
        set_tracer(self.original_tracer)
        if self.webhook_sitedir_path in sys.path:
            sys.path.remove(self.webhook_sitedir_path)

    def create_agent_and_setup_tracer(self):
        self.agent = HostAgent()
        self.span_recorder = StanRecorder(self.agent)
        self.tracer = InstanaTracer(recorder=self.span_recorder)
        set_agent(self.agent)
        set_tracer(self.tracer)

    def test_prepare_payload_basics(self):
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)

        self.assertEqual(len(payload.keys()), 3)
        self.assertIn('spans', payload)
        self.assertIsInstance(payload['spans'], list)
        self.assertEqual(len(payload['spans']), 0)
        self.assertIn('metrics', payload)
        self.assertEqual(len(payload['metrics'].keys()), 1)
        self.assertIn('plugins', payload['metrics'])
        self.assertIsInstance(payload['metrics']['plugins'], list)
        self.assertEqual(len(payload['metrics']['plugins']), 1)

        python_plugin = payload['metrics']['plugins'][0]
        self.assertEqual(python_plugin['name'], 'com.instana.plugin.python')
        self.assertEqual(python_plugin['entityId'], str(os.getpid()))
        self.assertIn('data', python_plugin)
        self.assertIn('snapshot', python_plugin['data'])
        self.assertIn('m', python_plugin['data']['snapshot'])
        self.assertEqual('Manual', python_plugin['data']['snapshot']['m'])
        self.assertIn('metrics', python_plugin['data'])

        # Validate that all metrics are reported on the first run
        self.assertIn('ru_utime', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_utime']), [float, int])
        self.assertIn('ru_stime', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_stime']), [float, int])
        self.assertIn('ru_maxrss', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_maxrss']), [float, int])
        self.assertIn('ru_ixrss', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_ixrss']), [float, int])
        self.assertIn('ru_idrss', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_idrss']), [float, int])
        self.assertIn('ru_isrss', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_isrss']), [float, int])
        self.assertIn('ru_minflt', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_minflt']), [float, int])
        self.assertIn('ru_majflt', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_majflt']), [float, int])
        self.assertIn('ru_nswap', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_nswap']), [float, int])
        self.assertIn('ru_inblock', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_inblock']), [float, int])
        self.assertIn('ru_oublock', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_oublock']), [float, int])
        self.assertIn('ru_msgsnd', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_msgsnd']), [float, int])
        self.assertIn('ru_msgrcv', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_msgrcv']), [float, int])
        self.assertIn('ru_nsignals', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_nsignals']), [float, int])
        self.assertIn('ru_nvcsw', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_nvcsw']), [float, int])
        self.assertIn('ru_nivcsw', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['ru_nivcsw']), [float, int])
        self.assertIn('alive_threads', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['alive_threads']), [float, int])
        self.assertIn('dummy_threads', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['dummy_threads']), [float, int])
        self.assertIn('daemon_threads', python_plugin['data']['metrics'])
        self.assertIn(type(python_plugin['data']['metrics']['daemon_threads']), [float, int])

        self.assertIn('gc', python_plugin['data']['metrics'])
        self.assertIsInstance(python_plugin['data']['metrics']['gc'], dict)
        self.assertIn('collect0', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['collect0']), [float, int])
        self.assertIn('collect1', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['collect1']), [float, int])
        self.assertIn('collect2', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['collect2']), [float, int])
        self.assertIn('threshold0', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['threshold0']), [float, int])
        self.assertIn('threshold1', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['threshold1']), [float, int])
        self.assertIn('threshold2', python_plugin['data']['metrics']['gc'])
        self.assertIn(type(python_plugin['data']['metrics']['gc']['threshold2']), [float, int])

    def test_prepare_payload_basics_disable_runtime_metrics(self):
        os.environ["INSTANA_DISABLE_METRICS_COLLECTION"] = "TRUE"
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)

        self.assertEqual(len(payload.keys()), 3)
        self.assertIn('spans', payload)
        self.assertIsInstance(payload['spans'], list)
        self.assertEqual(len(payload['spans']), 0)
        self.assertIn('metrics', payload)
        self.assertEqual(len(payload['metrics'].keys()), 1)
        self.assertIn('plugins', payload['metrics'])
        self.assertIsInstance(payload['metrics']['plugins'], list)
        self.assertEqual(len(payload['metrics']['plugins']), 1)

        python_plugin = payload['metrics']['plugins'][0]
        self.assertEqual(python_plugin['name'], 'com.instana.plugin.python')
        self.assertEqual(python_plugin['entityId'], str(os.getpid()))
        self.assertIn('data', python_plugin)
        self.assertIn('snapshot', python_plugin['data'])
        self.assertIn('m', python_plugin['data']['snapshot'])
        self.assertEqual('Manual', python_plugin['data']['snapshot']['m'])
        self.assertNotIn('metrics', python_plugin['data'])

    @patch.object(HostCollector, "should_send_snapshot_data")
    def test_prepare_payload_with_snapshot_with_python_packages(self, mock_should_send_snapshot_data):
        mock_should_send_snapshot_data.return_value = True
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)
        self.assertIn('snapshot', payload['metrics']['plugins'][0]['data'])
        snapshot =  payload['metrics']['plugins'][0]['data']['snapshot']
        self.assertTrue(snapshot)
        self.assertIn('m', snapshot)
        self.assertEqual('Manual', snapshot['m'])
        self.assertIn('version', snapshot)
        self.assertGreater(len(snapshot['versions']), 5)
        self.assertEqual(snapshot['versions']['instana'], VERSION)
        self.assertIn('wrapt', snapshot['versions'])
        self.assertIn('fysom', snapshot['versions'])
        self.assertIn('opentracing', snapshot['versions'])
        self.assertIn('basictracer', snapshot['versions'])

    @patch.object(HostCollector, "should_send_snapshot_data")
    def test_prepare_payload_with_snapshot_disabled_python_packages(self, mock_should_send_snapshot_data):
        mock_should_send_snapshot_data.return_value = True
        os.environ["INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION"] = "TRUE"
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)
        self.assertIn('snapshot', payload['metrics']['plugins'][0]['data'])
        snapshot =  payload['metrics']['plugins'][0]['data']['snapshot']
        self.assertTrue(snapshot)
        self.assertIn('m', snapshot)
        self.assertEqual('Manual', snapshot['m'])
        self.assertIn('version', snapshot)
        self.assertEqual(len(snapshot['versions']), 1)
        self.assertEqual(snapshot['versions']['instana'], VERSION)


    @patch.object(HostCollector, "should_send_snapshot_data")
    def test_prepare_payload_with_autowrapt(self, mock_should_send_snapshot_data):
        mock_should_send_snapshot_data.return_value = True
        os.environ["AUTOWRAPT_BOOTSTRAP"] = "instana"
        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)
        self.assertIn('snapshot', payload['metrics']['plugins'][0]['data'])
        snapshot =  payload['metrics']['plugins'][0]['data']['snapshot']
        self.assertTrue(snapshot)
        self.assertIn('m', snapshot)
        self.assertEqual('Autowrapt', snapshot['m'])
        self.assertIn('version', snapshot)
        self.assertGreater(len(snapshot['versions']), 5)
        expected_packages = ('instana', 'wrapt', 'fysom', 'opentracing', 'basictracer')
        for package in expected_packages:
            self.assertIn(package, snapshot['versions'], f"{package} not found in snapshot['versions']")
        self.assertEqual(snapshot['versions']['instana'], VERSION)


    @patch.object(HostCollector, "should_send_snapshot_data")
    def test_prepare_payload_with_autotrace(self, mock_should_send_snapshot_data):
        mock_should_send_snapshot_data.return_value = True

        sys.path.append(self.webhook_sitedir_path)

        self.create_agent_and_setup_tracer()

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)
        self.assertIn('snapshot', payload['metrics']['plugins'][0]['data'])
        snapshot =  payload['metrics']['plugins'][0]['data']['snapshot']
        self.assertTrue(snapshot)
        self.assertIn('m', snapshot)
        self.assertEqual('AutoTrace', snapshot['m'])
        self.assertIn('version', snapshot)
        self.assertGreater(len(snapshot['versions']), 5)
        expected_packages = ('instana', 'wrapt', 'fysom', 'opentracing', 'basictracer')
        for package in expected_packages:
            self.assertIn(package, snapshot['versions'], f"{package} not found in snapshot['versions']")
        self.assertEqual(snapshot['versions']['instana'], VERSION)
