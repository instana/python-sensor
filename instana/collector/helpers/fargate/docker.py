from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan


class DockerHelper(BaseHelper):
    def collect_metrics(self, with_snapshot = False):
        """
        Collect and return docker metrics (and optionally snapshot data) for this task
        @return: list - with one or more plugin entities
        """
        plugins = []
        try:
            if self.collector.task_metadata is not None:
                containers = self.collector.task_metadata.get("Containers", [])
                for container in containers:
                    plugin_data = dict()
                    plugin_data["name"] = "com.instana.plugin.docker"
                    try:
                        labels = container.get("Labels", {})
                        name = container.get("Name", "")
                        taskArn = labels.get("com.amazonaws.ecs.container-name", "")

                        # "entityId": $taskARN + "::" + $containerName
                        plugin_data["entityId"] = "%s::%s" % (taskArn, name)
                        plugin_data["data"] = DictionaryOfStan()

                        # Snapshot Data
                        plugin_data["data"]["Id"] = container.get("DockerId", None)
                        plugin_data["data"]["Created"] = container.get("CreatedAt", None)
                        plugin_data["data"]["Started"] = container.get("StartedAt", None)
                        plugin_data["data"]["Image"] = container.get("Image", None)
                        plugin_data["data"]["Labels"] = container.get("Labels", None)
                        plugin_data["data"]["Ports"] = container.get("Ports", None)

                        networks = container.get("Networks", [])
                        if len(networks) >= 1:
                            plugin_data["data"]["NetworkMode"] = networks[0].get("NetworkMode", None)
                    except:
                        logger.debug("_collect_container_snapshots: ", exc_info=True)
                    finally:
                        plugins.append(plugin_data)
        except:
            logger.debug("collect_docker_metrics: ", exc_info=True)
        return plugins
