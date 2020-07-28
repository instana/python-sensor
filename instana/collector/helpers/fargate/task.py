from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan


class TaskHelper(BaseHelper):
    def collect_metrics(self, with_snapshot = False):
        """
        Collect and return metrics data (and optionally snapshot data) for this task
        @return: list - with one plugin entity
        """
        plugin_data = dict()
        try:
            if self.collector.task_metadata is not None:
                plugin_data["name"] = "com.instana.plugin.aws.ecs.task"
                plugin_data["entityId"] = "metadata.TaskARN"  # FIXME
                plugin_data["data"] = DictionaryOfStan()
                plugin_data["data"]["taskArn"] = self.collector.task_metadata.get("TaskARN", None)
                plugin_data["data"]["clusterArn"] = self.collector.task_metadata.get("Cluster", None)
                plugin_data["data"]["taskDefinition"] = self.collector.task_metadata.get("Family", None)
                plugin_data["data"]["taskDefinitionVersion"] = self.collector.task_metadata.get("Revision", None)
                plugin_data["data"]["availabilityZone"] = self.collector.task_metadata.get("AvailabilityZone", None)
                plugin_data["data"]["desiredStatus"] = self.collector.task_metadata.get("DesiredStatus", None)
                plugin_data["data"]["knownStatus"] = self.collector.task_metadata.get("KnownStatus", None)
                plugin_data["data"]["pullStartedAt"] = self.collector.task_metadata.get("PullStartedAt", None)
                plugin_data["data"]["pullStoppedAt"] = self.collector.task_metadata.get("PullStoppeddAt", None)
                limits = self.collector.task_metadata.get("Limits", {})
                plugin_data["data"]["limits"]["cpu"] = limits.get("CPU", None)
                plugin_data["data"]["limits"]["memory"] = limits.get("Memory", None)
        except:
            logger.debug("collect_task_metrics: ", exc_info=True)
        return [plugin_data]
