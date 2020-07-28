import os
import json
import requests
import threading
from time import time
from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan, every, validate_url
from ..singletons import env_is_test

from .helpers.process.helper import ProcessHelper
from .helpers.runtime.helper import RuntimeHelper
from .helpers.fargate.task import TaskHelper
from .helpers.fargate.docker import DockerHelper
from .helpers.fargate.container import ContainerHelper


class AWSFargateCollector(BaseCollector):
    def __init__(self, agent):
        super(AWSFargateCollector, self).__init__(agent)
        logger.debug("Loading AWS Fargate Collector")

        # Indicates if this Collector has all requirements to run successfully
        self.ready_to_start = True

        # Prepare the URLS that we will collect data from
        self.ecmu = os.environ.get("ECS_CONTAINER_METADATA_URI", "")

        if self.ecmu == "" or validate_url(self.ecmu) is False:
            logger.warning("AWSFargateCollector: ECS_CONTAINER_METADATA_URI not in environment or invalid URL.  "
                        "Instana will not be able to monitor this environment")
            self.ready_to_start = False

        self.ecmu_url_root = self.ecmu
        self.ecmu_url_task = self.ecmu + '/task'
        self.ecmu_url_stats = self.ecmu + '/stats'
        self.ecmu_url_task_stats = self.ecmu + '/task/stats'

        # Lock used synchronize data collection
        self.ecmu_lock = threading.Lock()

        # How often to report data
        self.report_interval = 1
        self.http_client = requests.Session()

        # This is the collecter thread querying the metadata url
        self.ecs_metadata_thread = None

        # The fully qualified ARN for this process
        self._fq_arn = None

        # Saved snapshot data
        self.snapshot_data = None
        # Timestamp in seconds of the last time we sent snapshot data
        self.snapshot_data_last_sent = 0
        # How often to report snapshot data (in seconds)
        self.snapshot_data_interval = 600
        self.last_payload = None

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

        # List of helpers that help out in data collection
        self.helpers = []

        # Populate the collection helpers
        self.helpers.append(TaskHelper(self))
        self.helpers.append(DockerHelper(self))
        self.helpers.append(ProcessHelper(self))
        self.helpers.append(RuntimeHelper(self))
        self.helpers.append(ContainerHelper(self))

    def start(self):
        if self.ready_to_start is False:
            logger.warning("AWS Fargate Collector is missing requirements and cannot monitor this environment.")
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

        if env_is_test is True:
            # For test, we are using mock ECS metadata
            return

        lock_acquired = self.ecmu_lock.acquire(False)
        if lock_acquired:
            try:
                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/
                json_body = self.http_client.get(self.ecmu_url_root, timeout=3).content
                self.root_metadata = json.loads(json_body)

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/task
                json_body = self.http_client.get(self.ecmu_url_task, timeout=3).content
                self.task_metadata = json.loads(json_body)

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/stats
                json_body = self.http_client.get(self.ecmu_url_stats, timeout=3).content
                self.stats_metadata = json.loads(json_body)

                # Response from the last call to
                # ${ECS_CONTAINER_METADATA_URI}/task/stats
                json_body = self.http_client.get(self.ecmu_url_task_stats, timeout=3).content
                self.task_stats_metadata = json.loads(json_body)
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
        payload["spans"] = []
        payload["metrics"]["plugins"] = []

        if not self.span_queue.empty():
            payload["spans"] = self.queued_spans()

        plugins = []
        with_snapshot = self.should_send_snapshot_data()
        try:
            for helper in self.helpers:
                plugins.extend(helper.collect_metrics(with_snapshot))

            payload["metrics"]["plugins"] = plugins

            if with_snapshot is True:
                self.snapshot_data_last_sent = int(time())
        except:
            logger.debug("collect_snapshot error", exc_info=True)
        return payload

    def get_fq_arn(self):
        if self._fq_arn is not None:
            return self._fq_arn

        if self.root_metadata is not None:
            labels = self.root_metadata.get("Labels", None)
            if labels is not None:
                taskArn = labels.get("com.amazonaws.ecs.task-arn", "")

            container_name = self.root_metadata.get("Name", "")

            self._fq_arn = taskArn + "::" + container_name
            return self._fq_arn
        else:
            return "Missing ECMU metadata"
