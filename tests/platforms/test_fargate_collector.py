from __future__ import absolute_import

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
        assert(payload)

        assert(len(payload.keys()) == 2)
        assert('spans' in payload)
        assert(isinstance(payload['spans'], list))
        assert(len(payload['spans']) == 0)
        assert('metrics' in payload)
        assert(len(payload['metrics'].keys()) == 1)
        assert('plugins' in payload['metrics'])
        assert(isinstance(payload['metrics']['plugins'], list))
        assert(len(payload['metrics']['plugins']) == 7)

        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            # print("%s - %s" % (plugin["name"], plugin["entityId"]))
            assert('name' in plugin)
            assert('entityId' in plugin)
            assert('data' in plugin)

    def test_docker_plugin_snapshot_data(self):
        self.create_agent_and_setup_tracer()

        first_payload = self.agent.collector.prepare_payload()
        second_payload = self.agent.collector.prepare_payload()

        assert(first_payload)
        assert(second_payload)

        plugin_first_report = get_docker_plugin(first_payload['metrics']['plugins'])
        plugin_second_report = get_docker_plugin(second_payload['metrics']['plugins'])

        assert(plugin_first_report)
        assert("data" in plugin_first_report)

        # First report should have snapshot data
        data = plugin_first_report["data"]
        assert(data["Id"] == "63dc7ac9f3130bba35c785ed90ff12aad82087b5c5a0a45a922c45a64128eb45")
        assert(data["Created"] == "2020-07-27T12:14:12.583114444Z")
        assert(data["Started"] == "2020-07-27T12:14:13.545410186Z")
        assert(data["Image"] == "410797082306.dkr.ecr.us-east-2.amazonaws.com/fargate-docker-ssh:latest")
        assert(data["Labels"] == {'com.amazonaws.ecs.cluster': 'arn:aws:ecs:us-east-2:410797082306:cluster/lombardo-ssh-cluster', 'com.amazonaws.ecs.container-name': 'docker-ssh-aws-fargate', 'com.amazonaws.ecs.task-arn': 'arn:aws:ecs:us-east-2:410797082306:task/2d60afb1-e7fd-4761-9430-a375293a9b82', 'com.amazonaws.ecs.task-definition-family': 'docker-ssh-aws-fargate', 'com.amazonaws.ecs.task-definition-version': '1'})
        assert(data["Ports"] is None)

        # Second report should have no snapshot data
        assert(plugin_second_report)
        assert("data" in plugin_second_report)
        data = plugin_second_report["data"]
        assert("Id" in data)
        assert("Created" not in data)
        assert("Started" not in data)
        assert("Image" not in data)
        assert("Labels" not in data)
        assert("Ports" not in data)

    def test_docker_plugin_metrics(self):
        self.create_agent_and_setup_tracer()

        first_payload = self.agent.collector.prepare_payload()
        second_payload = self.agent.collector.prepare_payload()

        assert(first_payload)
        assert(second_payload)

        plugin_first_report = get_docker_plugin(first_payload['metrics']['plugins'])
        assert(plugin_first_report)
        assert("data" in plugin_first_report)

        plugin_second_report = get_docker_plugin(second_payload['metrics']['plugins'])
        assert(plugin_second_report)
        assert("data" in plugin_second_report)

        # First report should report all metrics
        data = plugin_first_report.get("data", None)
        assert(data)
        assert "network" not in data

        cpu = data.get("cpu", None)
        assert(cpu)
        assert(cpu["total_usage"] == 0.011033)
        assert(cpu["user_usage"] == 0.009918)
        assert(cpu["system_usage"] == 0.00089)
        assert(cpu["throttling_count"] == 0)
        assert(cpu["throttling_time"] == 0)

        memory = data.get("memory", None)
        assert(memory)
        assert(memory["active_anon"] == 78721024)
        assert(memory["active_file"] == 18501632)
        assert(memory["inactive_anon"] == 0)
        assert(memory["inactive_file"] == 71684096)
        assert(memory["total_cache"] == 90185728)
        assert(memory["total_rss"] == 78721024)
        assert(memory["usage"] == 193769472)
        assert(memory["max_usage"] == 195305472)
        assert(memory["limit"] == 536870912)

        blkio = data.get("blkio", None)
        assert(blkio)
        assert(blkio["blk_read"] == 0)
        assert(blkio["blk_write"] == 128352256)

        # Second report should report the delta (in the test case, nothing)
        data = plugin_second_report["data"]
        assert("cpu" in data)
        assert(len(data["cpu"]) == 0)
        assert("memory" in data)
        assert(len(data["memory"]) == 0)
        assert("blkio" in data)
        assert(len(data["blkio"]) == 1)
        assert(data["blkio"]['blk_write'] == 0)
        assert('blk_read' not in data["blkio"])

    def test_no_instana_zone(self):
        self.create_agent_and_setup_tracer()
        assert(self.agent.options.zone is None)

    def test_instana_zone(self):
        os.environ["INSTANA_ZONE"] = "YellowDog"
        self.create_agent_and_setup_tracer()

        assert(self.agent.options.zone == "YellowDog")

        payload = self.agent.collector.prepare_payload()
        assert(payload)

        plugins = payload['metrics']['plugins']
        assert(isinstance(plugins, list))

        task_plugin = None
        for plugin in plugins:
            if plugin["name"] == "com.instana.plugin.aws.ecs.task":
                task_plugin = plugin

        assert(task_plugin)
        assert("data" in task_plugin)
        assert("instanaZone" in task_plugin["data"])
        assert(task_plugin["data"]["instanaZone"] == "YellowDog")

    def test_custom_tags(self):
        os.environ["INSTANA_TAGS"] = "love,war=1,games"
        self.create_agent_and_setup_tracer()
        self.assertTrue(hasattr(self.agent.options, 'tags'))
        self.assertEqual(self.agent.options.tags, {"love": None, "war": "1", "games": None})

        payload = self.agent.collector.prepare_payload()

        assert payload
        task_plugin = None
        plugins = payload['metrics']['plugins']
        for plugin in plugins:
            if plugin["name"] == "com.instana.plugin.aws.ecs.task":
                task_plugin = plugin
        assert task_plugin
        assert "tags" in task_plugin["data"]
        tags = task_plugin["data"]["tags"]
        assert tags["war"] == "1"
        assert tags["love"] is None
        assert tags["games"] is None
