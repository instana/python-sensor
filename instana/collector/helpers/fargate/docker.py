from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan


class DockerHelper(BaseHelper):
    def __init__(self, collector):
        super(DockerHelper, self).__init__(collector)

        # The metrics from the previous report cycle
        self.previous = DictionaryOfStan()

    def collect_metrics(self, with_snapshot=False):
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
                    docker_id = container.get("DockerId")

                    name = container.get("Name", "")
                    labels = container.get("Labels", {})
                    task_arn = labels.get("com.amazonaws.ecs.task-arn", "")

                    plugin_data["entityId"] = "%s::%s" % (task_arn, name)
                    plugin_data["data"] = DictionaryOfStan()

                    # Metrics
                    self._collect_container_metrics(plugin_data, docker_id)

                    # Snapshot
                    if with_snapshot:
                        self._collect_container_snapshot(plugin_data, container)

                    plugins.append(plugin_data)
        except Exception:
            logger.debug("DockerHelper.collect_metrics: ", exc_info=True)
        return plugins

    def _collect_container_snapshot(self, plugin_data, container):
        try:
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
        except Exception:
            logger.debug("_collect_container_snapshot: ", exc_info=True)

    def _collect_container_metrics(self, plugin_data, docker_id):
        try:
            container = self.collector.task_stats_metadata.get(docker_id, None)
            if container is not None:
                # TODO
                # networks = container.get("networks", None)
                # if networks is not None:
                #     # sum of all delta(metadata.networks.$interface_ids.rx_bytes) for all interface IDs
                #     plugin_data["data"]["network"]["rx"]["bytes"] = 0
                #     plugin_data["data"]["network"]["rx"]["dropped"] = 0
                #     plugin_data["data"]["network"]["rx"]["errors"] = 0
                #     plugin_data["data"]["network"]["rx"]["packets"] = 0
                #     plugin_data["data"]["network"]["tx"]["bytes"] = 0
                #     plugin_data["data"]["network"]["tx"]["dropped"] = 0
                #     plugin_data["data"]["network"]["tx"]["errors"] = 0
                #     plugin_data["data"]["network"]["tx"]["packets"] = 0

                cpu_stats = container.get("cpu_stats", {})
                cpu_usage = cpu_stats.get("cpu_usage", None)
                throttling_data = cpu_stats.get("throttling_data", None)

                if cpu_usage is not None:
                    online_cpus = cpu_stats.get("online_cpus", 1)
                    system_cpu_usage = cpu_stats.get("system_cpu_usage", 0)

                    metric_value = (cpu_usage["total_usage"] / system_cpu_usage) * online_cpus
                    self.apply_delta(metric_value,
                                     self.previous[docker_id]["cpu"],
                                     plugin_data["data"]["cpu"], "total_usage")

                    metric_value = (cpu_usage["usage_in_usermode"] / system_cpu_usage) * online_cpus
                    self.apply_delta(metric_value,
                                     self.previous[docker_id]["cpu"],
                                     plugin_data["data"]["cpu"], "user_usage")

                    metric_value = (cpu_usage["usage_in_kernelmode"] / system_cpu_usage) * online_cpus
                    self.apply_delta(metric_value,
                                     self.previous[docker_id]["cpu"],
                                     plugin_data["data"]["cpu"], "system_usage")

                if throttling_data is not None:
                    self.apply_delta(throttling_data,
                                     self.previous[docker_id]["cpu"],
                                     plugin_data["data"]["cpu"], ("periods", "throttling_count"))
                    self.apply_delta(throttling_data,
                                     self.previous[docker_id]["cpu"],
                                     plugin_data["data"]["cpu"], ("throttled_time", "throttling_time"))

                memory = container.get("memory_stats", {})
                memory_stats = memory.get("stats", None)

                self.apply_delta(memory, self.previous[docker_id]["memory"], plugin_data["data"]["memory"], "usage")
                self.apply_delta(memory, self.previous[docker_id]["memory"], plugin_data["data"]["memory"], "max_usage")
                self.apply_delta(memory, self.previous[docker_id]["memory"], plugin_data["data"]["memory"], "limit")

                if memory_stats is not None:
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "active_anon")
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "active_file")
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "inactive_anon")
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "inactive_file")
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "total_cache")
                    self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                     plugin_data["data"]["memory"], "total_rss")

                blkio_stats = container.get("blkio_stats", None)
                if blkio_stats is not None:
                    service_bytes = blkio_stats.get("io_service_bytes_recursive", None)
                    if service_bytes is not None:
                        for entry in service_bytes:
                            if entry["op"] == "Read":
                                self.apply_delta(entry, self.previous[docker_id]["blkio"],
                                                 plugin_data["data"]["blkio"], ("value", "blk_read"))
                            elif entry["op"] == "Write":
                                self.apply_delta(entry, self.previous[docker_id]["blkio"],
                                                 plugin_data["data"]["blkio"], ("value", "blk_write"))

        except Exception:
            logger.debug("_collect_container_metrics: ", exc_info=True)
