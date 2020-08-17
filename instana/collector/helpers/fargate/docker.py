""" Module to handle the collection of Docker metrics in AWS Fargate """
from __future__ import division
from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan


class DockerHelper(BaseHelper):
    """ This class acts as a helper to collect Docker snapshot and metric information """
    def __init__(self, collector):
        super(DockerHelper, self).__init__(collector)

        # The metrics from the previous report cycle
        self.previous = DictionaryOfStan()

        # For metrics that are accumalative, store their previous values here
        # Indexed by docker_id:  self.previous_blkio[docker_id][metric]
        self.previous_blkio = DictionaryOfStan()

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
                    plugin_data["data"]["Id"] = container.get("DockerId", None)

                    # Metrics
                    self._collect_container_metrics(plugin_data, docker_id, with_snapshot)

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

    def _collect_container_metrics(self, plugin_data, docker_id, with_snapshot):
        container = self.collector.task_stats_metadata.get(docker_id, None)
        if container is not None:
            self._collect_network_metrics(container, plugin_data, docker_id, with_snapshot)
            self._collect_cpu_metrics(container, plugin_data, docker_id, with_snapshot)
            self._collect_memory_metrics(container, plugin_data, docker_id, with_snapshot)
            self._collect_blkio_metrics(container, plugin_data, docker_id, with_snapshot)

    def _collect_network_metrics(self, container, plugin_data, docker_id, with_snapshot):
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
                                 plugin_data["data"]["tx"], "bytes", with_snapshot)
                self.apply_delta(tx_dropped_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "dropped", with_snapshot)
                self.apply_delta(tx_errors_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "errors", with_snapshot)
                self.apply_delta(tx_packets_total, self.previous[docker_id]["network"]["tx"],
                                 plugin_data["data"]["tx"], "packets", with_snapshot)

                self.apply_delta(rx_bytes_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "bytes", with_snapshot)
                self.apply_delta(rx_dropped_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "dropped", with_snapshot)
                self.apply_delta(rx_errors_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "errors", with_snapshot)
                self.apply_delta(rx_packets_total, self.previous[docker_id]["network"]["rx"],
                                 plugin_data["data"]["rx"], "packets", with_snapshot)
        except Exception:
            logger.debug("_collect_network_metrics: ", exc_info=True)

    def _collect_cpu_metrics(self, container, plugin_data, docker_id, with_snapshot):
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
                                 plugin_data["data"]["cpu"], "total_usage", with_snapshot)

                metric_value = (cpu_usage["usage_in_usermode"] / system_cpu_usage) * online_cpus
                self.apply_delta(round(metric_value, 6),
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], "user_usage", with_snapshot)

                metric_value = (cpu_usage["usage_in_kernelmode"] / system_cpu_usage) * online_cpus
                self.apply_delta(round(metric_value, 6),
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], "system_usage", with_snapshot)

            if throttling_data is not None:
                self.apply_delta(throttling_data,
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], ("periods", "throttling_count"), with_snapshot)
                self.apply_delta(throttling_data,
                                 self.previous[docker_id]["cpu"],
                                 plugin_data["data"]["cpu"], ("throttled_time", "throttling_time"), with_snapshot)
        except Exception:
            logger.debug("_collect_cpu_metrics: ", exc_info=True)

    def _collect_memory_metrics(self, container, plugin_data, docker_id, with_snapshot):
        try:
            memory = container.get("memory_stats", {})
            memory_stats = memory.get("stats", None)

            self.apply_delta(memory, self.previous[docker_id]["memory"],
                             plugin_data["data"]["memory"], "usage", with_snapshot)
            self.apply_delta(memory, self.previous[docker_id]["memory"],
                             plugin_data["data"]["memory"], "max_usage", with_snapshot)
            self.apply_delta(memory, self.previous[docker_id]["memory"],
                             plugin_data["data"]["memory"], "limit", with_snapshot)

            if memory_stats is not None:
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "active_anon", with_snapshot)
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "active_file", with_snapshot)
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "inactive_anon", with_snapshot)
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "inactive_file", with_snapshot)
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "total_cache", with_snapshot)
                self.apply_delta(memory_stats, self.previous[docker_id]["memory"],
                                 plugin_data["data"]["memory"], "total_rss", with_snapshot)
        except Exception:
            logger.debug("_collect_memory_metrics: ", exc_info=True)

    def _collect_blkio_metrics(self, container, plugin_data, docker_id, with_snapshot):
        try:
            blkio_stats = container.get("blkio_stats", None)
            if blkio_stats is not None:
                service_bytes = blkio_stats.get("io_service_bytes_recursive", None)
                if service_bytes is not None:
                    for entry in service_bytes:
                        if entry["op"] == "Read":
                            previous_value = self.previous_blkio[docker_id].get("blk_read", 0)
                            value_diff = entry["value"] - previous_value
                            self.apply_delta(value_diff, self.previous[docker_id]["blkio"],
                                             plugin_data["data"]["blkio"], "blk_read", with_snapshot)
                            self.previous_blkio[docker_id]["blk_read"] = entry["value"]
                        elif entry["op"] == "Write":
                            previous_value = self.previous_blkio[docker_id].get("blk_write", 0)
                            value_diff = entry["value"] - previous_value
                            self.apply_delta(value_diff, self.previous[docker_id]["blkio"],
                                             plugin_data["data"]["blkio"], "blk_write", with_snapshot)
                            self.previous_blkio[docker_id]["blk_write"] = entry["value"]
        except Exception:
            logger.debug("_collect_blkio_metrics: ", exc_info=True)
