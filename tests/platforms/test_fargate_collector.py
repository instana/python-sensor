# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import json
import unittest

from instana.tracer import InstanaTracer
from instana.recorder import StanRecorder
from instana.agent.aws_fargate import AWSFargateAgent
from instana.singletons import get_agent, set_agent, get_tracer, set_tracer


def get_docker_plugin(plugins):
    """
    Given a list of plugins, find and return the docker plugin that we're interested in from the mock data
    """
    docker_plugin = None
    for plugin in plugins:
        if plugin["name"] == "com.instana.plugin.docker" and plugin["entityId"] == "arn:aws:ecs:us-east-2:410797082306:task/2d60afb1-e7fd-4761-9430-a375293a9b82::docker-ssh-aws-fargate":
            docker_plugin = plugin
    return docker_plugin


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
        os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"
        os.environ["INSTANA_ENDPOINT_URL"] = "https://localhost/notreal"
        os.environ["INSTANA_AGENT_KEY"] = "Fake_Key"

        if "INSTANA_ZONE" in os.environ:
            os.environ.pop("INSTANA_ZONE")
        if "INSTANA_TAGS" in os.environ:
            os.environ.pop("INSTANA_TAGS")

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
        self.assertEqual(7, len(payload['metrics']['plugins']))

        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            # print("%s - %s" % (plugin["name"], plugin["entityId"]))
            self.assertIn('name', plugin)
            self.assertIn('entityId', plugin)
            self.assertIn('data', plugin)

    def test_docker_plugin_snapshot_data(self):
        self.create_agent_and_setup_tracer()

        first_payload = self.agent.collector.prepare_payload()
        second_payload = self.agent.collector.prepare_payload()

        self.assertTrue(first_payload)
        self.assertTrue(second_payload)

        plugin_first_report = get_docker_plugin(first_payload['metrics']['plugins'])
        plugin_second_report = get_docker_plugin(second_payload['metrics']['plugins'])

        self.assertTrue(plugin_first_report)
        self.assertIn("data", plugin_first_report)

        # First report should have snapshot data
        data = plugin_first_report["data"]
        self.assertEqual(data["Id"], "63dc7ac9f3130bba35c785ed90ff12aad82087b5c5a0a45a922c45a64128eb45")
        self.assertEqual(data["Created"], "2020-07-27T12:14:12.583114444Z")
        self.assertEqual(data["Started"], "2020-07-27T12:14:13.545410186Z")
        self.assertEqual(data["Image"], "410797082306.dkr.ecr.us-east-2.amazonaws.com/fargate-docker-ssh:latest")
        self.assertEqual(data["Labels"], {'com.amazonaws.ecs.cluster': 'arn:aws:ecs:us-east-2:410797082306:cluster/lombardo-ssh-cluster', 'com.amazonaws.ecs.container-name': 'docker-ssh-aws-fargate', 'com.amazonaws.ecs.task-arn': 'arn:aws:ecs:us-east-2:410797082306:task/2d60afb1-e7fd-4761-9430-a375293a9b82', 'com.amazonaws.ecs.task-definition-family': 'docker-ssh-aws-fargate', 'com.amazonaws.ecs.task-definition-version': '1'})
        self.assertIsNone(data["Ports"])

        # Second report should have no snapshot data
        self.assertTrue(plugin_second_report)
        self.assertIn("data", plugin_second_report)
        data = plugin_second_report["data"]
        self.assertIn("Id", data)
        self.assertNotIn("Created", data)
        self.assertNotIn("Started", data)
        self.assertNotIn("Image", data)
        self.assertNotIn("Labels", data)
        self.assertNotIn("Ports", data)

    def test_docker_plugin_metrics(self):
        self.create_agent_and_setup_tracer()

        first_payload = self.agent.collector.prepare_payload()
        second_payload = self.agent.collector.prepare_payload()

        self.assertTrue(first_payload)
        self.assertTrue(second_payload)

        plugin_first_report = get_docker_plugin(first_payload['metrics']['plugins'])
        self.assertTrue(plugin_first_report)
        self.assertIn("data", plugin_first_report)

        plugin_second_report = get_docker_plugin(second_payload['metrics']['plugins'])
        self.assertTrue(plugin_second_report)
        self.assertIn("data", plugin_second_report)

        # First report should report all metrics
        data = plugin_first_report.get("data", None)
        self.assertTrue(data)
        self.assertNotIn("network", data)

        cpu = data.get("cpu", None)
        self.assertTrue(cpu)
        self.assertEqual(cpu["total_usage"], 0.011033)
        self.assertEqual(cpu["user_usage"], 0.009918)
        self.assertEqual(cpu["system_usage"], 0.00089)
        self.assertEqual(cpu["throttling_count"], 0)
        self.assertEqual(cpu["throttling_time"], 0)

        memory = data.get("memory", None)
        self.assertTrue(memory)
        self.assertEqual(memory["active_anon"], 78721024)
        self.assertEqual(memory["active_file"], 18501632)
        self.assertEqual(memory["inactive_anon"], 0)
        self.assertEqual(memory["inactive_file"], 71684096)
        self.assertEqual(memory["total_cache"], 90185728)
        self.assertEqual(memory["total_rss"], 78721024)
        self.assertEqual(memory["usage"], 193769472)
        self.assertEqual(memory["max_usage"], 195305472)
        self.assertEqual(memory["limit"], 536870912)

        blkio = data.get("blkio", None)
        self.assertTrue(blkio)
        self.assertEqual(blkio["blk_read"], 0)
        self.assertEqual(blkio["blk_write"], 128352256)

        # Second report should report the delta (in the test case, nothing)
        data = plugin_second_report["data"]
        self.assertIn("cpu", data)
        self.assertEqual(len(data["cpu"]), 0)
        self.assertIn("memory", data)
        self.assertEqual(len(data["memory"]), 0)
        self.assertIn("blkio", data)
        self.assertEqual(len(data["blkio"]), 1)
        self.assertEqual(data["blkio"]['blk_write'], 0)
        self.assertNotIn('blk_read', data["blkio"])

    def test_no_instana_zone(self):
        self.create_agent_and_setup_tracer()
        self.assertIsNone(self.agent.options.zone)

    def test_instana_zone(self):
        os.environ["INSTANA_ZONE"] = "YellowDog"
        self.create_agent_and_setup_tracer()

        self.assertEqual(self.agent.options.zone, "YellowDog")

        payload = self.agent.collector.prepare_payload()
        self.assertTrue(payload)

        plugins = payload['metrics']['plugins']
        self.assertIsInstance(plugins, list)

        task_plugin = None
        for plugin in plugins:
            if plugin["name"] == "com.instana.plugin.aws.ecs.task":
                task_plugin = plugin

        self.assertTrue(task_plugin)
        self.assertIn("data", task_plugin)
        self.assertIn("instanaZone", task_plugin["data"])
        self.assertEqual(task_plugin["data"]["instanaZone"], "YellowDog")

    def test_custom_tags(self):
        os.environ["INSTANA_TAGS"] = "love,war=1,games"
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'tags'))
        self.assertDictEqual(self.agent.options.tags, {"love": None, "war": "1", "games": None})

        payload = self.agent.collector.prepare_payload()

        self.assertTrue(payload)
        task_plugin = None
        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            if plugin["name"] == "com.instana.plugin.aws.ecs.task":
                task_plugin = plugin
        self.assertTrue(task_plugin)
        self.assertIn("tags", task_plugin["data"])
        tags = task_plugin["data"]["tags"]
        self.assertEqual(tags["war"], "1")
        self.assertIsNone(tags["love"])
        self.assertIsNone(tags["games"])
