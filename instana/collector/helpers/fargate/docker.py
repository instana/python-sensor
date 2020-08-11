""" Module to handle the collection of Docker metrics in AWS Fargate """
from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan, to_pretty_json


class DockerHelper(BaseHelper):
    """ This class acts as a helper to collect Docker snapshot and metric information """
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
                    #logger.debug(to_pretty_json(plugin_data))
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
        container = self.collector.task_stats_metadata.get(docker_id, None)
        if container is not None:
            self._collect_network_metrics(container, plugin_data, docker_id)
            self._collect_cpu_metrics(container, plugin_data, docker_id)
            self._collect_memory_metrics(container, plugin_data, docker_id)
            self._collect_blkio_metrics(container, plugin_data, docker_id)

    def _collect_network_metrics(self, container, plugin_data, docker_id):
        try:
            networks = container.get("networks", None)
            tx_bytes_total = tx_dropped_total = tx_errors_total = tx_packets_total = 0
            rx_bytes_total = rx_dropped_total = rx_errors_total = rx_packets_total = 0

            if networks is not None:
                for key in networks.keys():
                    if "eth" in key:
                        tx_bytes_total += networks[key].get("tx_bytes", 0)
                        tx_dropped_total += networks[key].get("tx_dropped", 0)
                        tx_errors_total += networks[key].get("tx_errors", 0)
                        tx_packets_total += networks[key].get("tx_packets", 0)

                        rx_bytes_total += networks[key].get("rx_bytes", 0)
                        rx_dropped_total += networks[key].get("rx_dropped", 0)
                        rx_errors_total += networks[key].get("rx_errors", 0)
                        rx_packets_total += networks[key].get("rx_packets", 0)

                self.apply_delta(tx_bytes_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "bytes")
                self.apply_delta(tx_dropped_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "dropped")
                self.apply_delta(tx_errors_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "errors")
                self.apply_delta(tx_packets_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "packets")

                self.apply_delta(rx_bytes_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "bytes")
                self.apply_delta(rx_dropped_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "dropped")
                self.apply_delta(rx_errors_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "errors")
                self.apply_delta(rx_packets_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "packets")
        except Exception:
            logger.debug("_collect_network_metrics: ", exc_info=True)

    def _collect_cpu_metrics(self, container, plugin_data, docker_id):
        try:
            cpu_stats = container.get("cpu_stats", {})
            cpu_usage = cpu_stats.get("cpu_usage", None)
            throttling_data = cpu_stats.get("throttling_data", None)

            if cpu_usage is not None:
                online_cpus = cpu_stats.get("online_cpus", 1)
                system_cpu_usage = cpu_stats.get("system_cpu_usage", 0)

                metric_value = (cpu_usage["total_usage"] / system_cpu_usage) * online_cpus
                self.apply_delta(round(metric_value, 6),
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], "total_usage")

                metric_value = (cpu_usage["usage_in_usermode"] / system_cpu_usage) * online_cpus
                self.apply_delta(round(metric_value, 6),
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], "user_usage")

                metric_value = (cpu_usage["usage_in_kernelmode"] / system_cpu_usage) * online_cpus
                self.apply_delta(round(metric_value, 6),
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], "system_usage")

            if throttling_data is not None:
                self.apply_delta(throttling_data,
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], ("periods", "throttling_count"))
                self.apply_delta(throttling_data,
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], ("throttled_time", "throttling_time"))
        except Exception:
            logger.debug("_collect_cpu_metrics: ", exc_info=True)

    def _collect_memory_metrics(self, container, plugin_data, docker_id):
        try:
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
        except Exception:
            logger.debug("_collect_memory_metrics: ", exc_info=True)

    def _collect_blkio_metrics(self, container, plugin_data, docker_id):
        try:
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
            logger.debug("_collect_blkio_metrics: ", exc_info=True)
