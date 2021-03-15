# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

""" Module to handle the collection of container metrics in AWS Fargate """
from ....log import logger
from ....util import DictionaryOfStan
from ..base import BaseHelper


class ContainerHelper(BaseHelper):
    """ This class acts as a helper to collect container snapshot and metric information """
    def collect_metrics(self, with_snapshot=False):
        """
        Collect and return metrics (and optionally snapshot data) for every container in this task
        @return: list - with one or more plugin entities
        """
        plugins = []

        try:
            if self.collector.task_metadata is not None:
                containers = self.collector.task_metadata.get("Containers", [])
                for container in containers:
                    plugin_data = dict()
                    plugin_data["name"] = "com.instana.plugin.aws.ecs.container"
                    try:
                        labels = container.get("Labels", {})
                        name = container.get("Name", "")
                        task_arn = labels.get("com.amazonaws.ecs.task-arn", "")
                        plugin_data["entityId"] = "%s::%s" % (task_arn, name)

                        plugin_data["data"] = DictionaryOfStan()
                        if self.collector.root_metadata["Name"] == name:
                            plugin_data["data"]["instrumented"] = True
                        plugin_data["data"]["dockerId"] = container.get("DockerId", None)
                        plugin_data["data"]["taskArn"] = labels.get("com.amazonaws.ecs.task-arn", None)

                        if with_snapshot is True:
                            plugin_data["data"]["runtime"] = "python"
                            plugin_data["data"]["dockerName"] = container.get("DockerName", None)
                            plugin_data["data"]["containerName"] = container.get("Name", None)
                            plugin_data["data"]["image"] = container.get("Image", None)
                            plugin_data["data"]["imageId"] = container.get("ImageID", None)
                            plugin_data["data"]["taskDefinition"] = labels.get("com.amazonaws.ecs.task-definition-family", None)
                            plugin_data["data"]["taskDefinitionVersion"] = labels.get("com.amazonaws.ecs.task-definition-version", None)
                            plugin_data["data"]["clusterArn"] = labels.get("com.amazonaws.ecs.cluster", None)
                            plugin_data["data"]["desiredStatus"] = container.get("DesiredStatus", None)
                            plugin_data["data"]["knownStatus"] = container.get("KnownStatus", None)
                            plugin_data["data"]["ports"] = container.get("Ports", None)
                            plugin_data["data"]["createdAt"] = container.get("CreatedAt", None)
                            plugin_data["data"]["startedAt"] = container.get("StartedAt", None)
                            plugin_data["data"]["type"] = container.get("Type", None)
                            limits = container.get("Limits", {})
                            plugin_data["data"]["limits"]["cpu"] = limits.get("CPU", None)
                            plugin_data["data"]["limits"]["memory"] = limits.get("Memory", None)
                    except Exception:
                        logger.debug("_collect_container_snapshots: ", exc_info=True)
                    finally:
                        plugins.append(plugin_data)
        except Exception:
            logger.debug("collect_container_metrics: ", exc_info=True)
        return plugins
