import os
import getpass
import requests
import threading
from time import time
from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan, get_proc_cmdline, every, validate_url


class AWSFargateCollector(BaseCollector):
    def __init__(self, agent):
        super(AWSFargateCollector, self).__init__(agent)
        logger.debug("Loading AWS Fargate Collector")

        # Indicates if this Collector has all requirements to run successfully
        self.ready_to_start = True

        # Prepare the URLS that we will collect data from
        self.ecmu = os.environ.get("ECS_CONTAINER_METADATA_URI", "")

        if self.ecmu == "" or validate_url(self.ecmu) is False:
            logger.warn("AWSFargateCollector: ECS_CONTAINER_METADATA_URI not in environment or invalid URL.  "
                        "Instana will not be able to monitor this environment")
            self.ready_to_start = False

        self.ecmu_url_root = self.ecmu + '/'
        self.ecmu_url_task = self.ecmu + '/task'
        self.ecmu_url_stats = self.ecmu + '/stats'
        self.ecmu_url_task_stats = self.ecmu + '/task/stats'

        # Lock used synchronize data collection
        self.ecmu_lock = threading.Lock()

        # How often to report data
        self.report_interval = 1
        self.http_client = requests.Session()

        # Saved snapshot data
        self.snapshot_data = None
        # Timestamp in seconds of the last time we sent snapshot data
        self.snapshot_data_last_sent = 0
        # How often to report snapshot data (in seconds)
        self.snapshot_data_interval = 600

        # Response from the last call to
        # ${ECS_CONTAINER_METADATA_URI}/
        self.root_metadata = None

        # Response from the last call to
        # ${ECS_CONTAINER_METADATA_URI}/task
        self.task_metadata = None

        # Response from the last call to
        # ${ECS_CONTAINER_METADATA_URI}/stats
        self.stats_metadata = None

        # Response from the last call to
        # ${ECS_CONTAINER_METADATA_URI}/task/stats
        self.task_stats_metadata = None

    def start(self):
        if self.ready_to_start is False:
            logger.warn("AWS Fargate Collector is missing requirements and cannot monitor this environment.")
            return

        # Launch a thread here to periodically collect data from the ECS Metadata Container API
        if self.agent.can_send():
            logger.debug("AWSFargateCollector.start: launching ecs metadata collection thread")
            self.ecs_metadata_thread = threading.Thread(target=self.metadata_thread_loop, args=())
            self.ecs_metadata_thread.setDaemon(True)
            self.ecs_metadata_thread.start()
        else:
            logger.warning("Collector started but the agent tells us we can't send anything out.")

        super(AWSFargateCollector, self).start()

    def metadata_thread_loop(self):
        """
        Just a loop that is run in the background thread.
        @return: None
        """
        every(self.report_interval, self.get_ecs_metadata, "AWSFargateCollector: metadata_thread_loop")

    def get_ecs_metadata(self):
        """
        Get the latest data from the ECS metadata container API and store on the class
        @return: Boolean
        """
        lock_acquired = self.ecmu_lock.acquire(False)
        if lock_acquired:
            try:
                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/
                self.root_metadata = self.http_client.get(self.ecmu_url_root, timeout=3).content

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/task
                self.task_metadata = self.http_client.get(self.ecmu_url_task, timeout=3).content

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/stats
                self.stats_metadata = self.http_client.get(self.ecmu_url_stats, timeout=3).content

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/task/stats
                self.task_stats_metadata = self.http_client.get(self.ecmu_url_task_stats, timeout=3).content
            except Exception:
                logger.debug("AWSFargateCollector.get_ecs_metadata", exc_info=True)
            finally:
                self.ecmu_lock.release()
        else:
            logger.debug("AWSFargateCollector.get_ecs_metadata: skipping because data collection already in progress")

    def should_send_snapshot_data(self):
        delta = int(time()) - self.snapshot_data_last_sent
        if delta > self.snapshot_data_interval:
            return True
        return False

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = None
        payload["metrics"] = None

        if not self.span_queue.empty():
            payload["spans"] = self.__queued_spans()

        if self.should_send_snapshot_data():
            if self.snapshot_data is None:
                self.snapshot_data = self.collect_snapshot()
            payload["metrics"] = self.snapshot_data
            self.snapshot_data_last_sent = int(time())

        return payload

    def collect_snapshot(self, *argv, **kwargs):
        plugins = []
        self.snapshot_data = DictionaryOfStan()

        try:
            plugins.extend(self._collect_task_snapshot())
            plugins.extend(self._collect_container_snapshots())
            plugins.extend(self._collect_docker_snapshot())
            plugins.extend(self._collect_process_snapshot())
            plugins.extend(self._collect_runtime_snapshot())
            self.snapshot_data["plugins"] = plugins
        except:
            logger.debug("collect_snapshot error", exc_info=True)
        finally:
            return self.snapshot_data

    def _collect_task_snapshot(self):
        """
        Collect and return snapshot data for the task
        @return: list - with one plugin entity
        """
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.aws.ecs.task"
            plugin_data["entityId"] = "metadata.TaskARN" # FIXME
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["taskArn"] = self.task_metadata.get("TaskARN", None)
            plugin_data["data"]["clusterArn"] = self.task_metadata.get("Cluster", None)
            plugin_data["data"]["taskDefinition"] = self.task_metadata.get("Family", None)
            plugin_data["data"]["taskDefinitionVersion"] = self.task_metadata.get("Revision", None)
            plugin_data["data"]["availabilityZone"] = self.task_metadata.get("AvailabilityZone", None)
            plugin_data["data"]["desiredStatus"] = self.task_metadata.get("DesiredStatus", None)
            plugin_data["data"]["knownStatus"] = self.task_metadata.get("KnownStatus", None)
            plugin_data["data"]["pullStartedAt"] = self.task_metadata.get("PullStartedAt", None)
            plugin_data["data"]["pullStoppedAt"] = self.task_metadata.get("PullStoppeddAt", None)
            limits = self.task_metadata.get("Limits", {})
            plugin_data["data"]["limits"]["cpu"] = limits.get("CPU", None)
            plugin_data["data"]["limits"]["memory"] = limits.get("Memory", None)
        except:
            logger.debug("_collect_task_snapshot: ", exc_info=True)
        return [plugin_data]

    def _collect_container_snapshots(self):
        """
        Collect and return snapshot data for every container in this task
        @return: list - with one or more plugin entities
        """
        plugins = []
        try:
            containers = self.task_metadata.get("Containers", [])
            for container in containers:
                plugin_data = dict()
                try:
                    labels = container.get("Labels", {})
                    name = container.get("Name", "")
                    taskArn = labels.get("com.amazonaws.ecs.container-name", "")

                    plugin_data["name"] = "com.instana.plugin.aws.ecs.container"
                    # "entityId": $taskARN + "::" + $containerName
                    plugin_data["entityId"] = "%s::%s" % (taskArn, name)

                    plugin_data["data"] = DictionaryOfStan()
                    if self.root_metadata["Name"] == name:
                        plugin_data["data"]["instrumented"] = True
                    plugin_data["data"]["runtime"] = "python"
                    plugin_data["data"]["dockerId"] = container.get("DockerId", None)
                    plugin_data["data"]["dockerName"] = container.get("DockerName", None)
                    plugin_data["data"]["containerName"] = container.get("Name", None)
                    plugin_data["data"]["image"] = container.get("Image", None)
                    plugin_data["data"]["imageId"] = container.get("ImageID", None)
                    plugin_data["data"]["taskArn"] = labels.get("com.amazonaws.ecs.task-arn", None)
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
                except:
                    logger.debug("_collect_container_snapshots: ", exc_info=True)
                finally:
                    plugins.append(plugin_data)
        except:
            logger.debug("_collect_container_snapshots: ", exc_info=True)
        return plugins

    def _collect_docker_snapshot(self):
        plugins = []
        try:
            containers = self.task_metadata.get("Containers", [])
            for container in containers:
                plugin_data = dict()
                try:
                    labels = container.get("Labels", {})
                    name = container.get("Name", "")
                    taskArn = labels.get("com.amazonaws.ecs.container-name", "")

                    plugin_data["name"] = "com.instana.plugin.docker"
                    # "entityId": $taskARN + "::" + $containerName
                    plugin_data["entityId"] = "%s::%s" % (taskArn, name)
                    plugin_data["data"] = DictionaryOfStan()
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
            logger.debug("_collect_container_snapshots: ", exc_info=True)
        return plugins

    def _collect_process_snapshot(self):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.process"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["pid"] = int(os.getpid())
            env = dict()
            for key in os.environ:
                env[key] = os.environ[key]
            plugin_data["data"]["env"] = env
            plugin_data["data"]["exec"] = os.readlink("/proc/self/exe")

            cmdline = get_proc_cmdline()
            if len(cmdline) > 1:
                # drop the exe
                cmdline.pop(0)
            plugin_data["data"]["args"] = cmdline
            plugin_data["data"]["user"] = getpass.getuser()
            try:
                plugin_data["data"]["group"] = getpass.getuser(os.getegid()).gr_name
            except:
                logger.debug("getpass.getuser: ", exc_info=True)

            plugin_data["data"]["start"] = 1 # ¯\_(ツ)_/¯ FIXME
            plugin_data["data"]["containerType"] = "docker"
            plugin_data["data"]["container"] = self.root_metadata.get("DockerId")
            plugin_data["data"]["com.instana.plugin.host.pid"] = 1 # ¯\_(ツ)_/¯ FIXME
            plugin_data["data"]["com.instana.plugin.host.name"] = self.task_metadata.get("TaskArn")


        except:
            logger.debug("_collect_process_snapshot: ", exc_info=True)
        return plugin_data

    def _collect_runtime_snapshot(self):
        plugin_data = dict()
        lock_acquired = self.process_metadata_mutex.acquire(False)
        if lock_acquired:
            try:
                plugin_data["name"] = "com.instana.plugin.python"
                plugin_data["entityId"] = str(os.getpid())
                plugin_data["data"] = DictionaryOfStan()
            except:
                logger.debug("_collect_runtime_snapshot: ", exc_info=True)
            finally:
                self.process_metadata_mutex.release()
        return plugin_data
