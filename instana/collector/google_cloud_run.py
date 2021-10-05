# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

"""
Google Cloud Run Collector: Manages the periodic collection of metrics & snapshot data
"""
import os
import json
from time import time
import requests

from instana.log import logger
from instana.collector.base import BaseCollector
from instana.util import DictionaryOfStan, validate_url
from instana.singletons import env_is_test

from instana.collector.helpers.google_cloud_run.process import GCRProcessHelper
from instana.collector.helpers.google_cloud_run.instance_entity import InstanceEntityHelper


class GCRCollector(BaseCollector):
    """ Collector for Google Cloud Run """

    def __init__(self, agent):
        super(GCRCollector, self).__init__(agent)
        logger.debug("Loading Google Cloud Run Collector")

        # Indicates if this Collector has all requirements to run successfully
        self.ready_to_start = True

        self.revision = os.environ.get("K_REVISION")
        self.service = os.environ.get("K_SERVICE")
        self.configuration = os.environ.get("K_CONFIGURATION")
        # Prepare the URLS that we will collect data from
        self.gcr_md_uri = os.environ.get("GOOGLE_CLOUD_RUN_METADATA_ENDPOINT", "http://metadata.google.internal")

        if self.gcr_md_uri == "" or validate_url(self.gcr_md_uri) is False:
            logger.warning("GCRCollector: GOOGLE_CLOUD_RUN_METADATA_ENDPOINT not in environment or invalid URL.  "
                           "Instana will not be able to monitor this environment")
            self.ready_to_start = False

        self.gcr_md_project_uri = self.gcr_md_uri + '/computeMetadata/v1/project/?recursive=true'
        self.gcr_md_instance_uri = self.gcr_md_uri + '/computeMetadata/v1/instance/?recursive=true'

        # Timestamp in seconds of the last time we fetched all GCR metadata
        self.last_gcr_md_full_fetch = 0

        # How often to do a full fetch of GCR metadata
        self.gcr_md_full_fetch_interval = 300

        # HTTP client with keep-alive
        self.http_client = requests.Session()

        # This is the collector thread querying the metadata url
        self.gcr_metadata_thread = None

        # The fully qualified ARN for this process
        self._gcp_arn = None

        # Response from the last call to
        # Instance URI
        self.instance_metadata = None

        # Response from the last call to
        # Project URI
        self.project_metadata = None

        # Populate the collection helpers
        self.helpers.append(GCRProcessHelper(self))
        self.helpers.append(InstanceEntityHelper(self))

    def start(self):
        if self.ready_to_start is False:
            logger.warning("Google Cloud Run Collector is missing requirements and cannot monitor this environment.")
            return

        super(GCRCollector, self).start()

    def get_project_instance_metadata(self):
        """
        Get the latest data from the service revision instance entity metadata and store in the class
        @return: Boolean
        """
        if env_is_test is True:
            # For test, we are using mock service revision instance entity metadata
            return

        try:
            delta = int(time()) - self.last_gcr_md_full_fetch
            if delta > self.gcr_md_full_fetch_interval:
                # Refetch the GCR snapshot data
                self.last_gcr_md_full_fetch = int(time())
                headers = {"Metadata-Flavor": "Google"}
                # Response from the last call to
                # ${GOOGLE_CLOUD_RUN_METADATA_ENDPOINT}/computeMetadata/v1/project/?recursive=true
                json_body = self.http_client.get(self.gcr_md_project_uri, timeout=1, headers=headers).content
                self.project_metadata = json.loads(json_body)

                # Response from the last call to
                # ${GOOGLE_CLOUD_RUN_METADATA_ENDPOINT}/computeMetadata/v1/instance/?recursive=true
                json_body = self.http_client.get(self.gcr_md_instance_uri, timeout=1, headers=headers).content
                self.instance_metadata = json.loads(json_body)
        except Exception:
            logger.debug("GoogleCloudRunCollector.get_project_instance_metadata", exc_info=True)

    def should_send_snapshot_data(self):
        delta = int(time()) - self.snapshot_data_last_sent
        if delta > self.snapshot_data_interval:
            return True
        return False

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = []
        payload["metrics"]["plugins"] = []

        try:
            if not self.span_queue.empty():
                payload["spans"] = self.queued_spans()

            with_snapshot = self.should_send_snapshot_data()

            # Fetch the latest metrics
            self.get_project_instance_metadata()

            plugins = []
            for helper in self.helpers:
                plugins.extend(helper.collect_metrics(with_snapshot))

            payload["metrics"]["plugins"] = plugins

            if with_snapshot is True:
                self.snapshot_data_last_sent = int(time())
        except Exception:
            logger.debug("collect_snapshot error", exc_info=True)

        return payload

    def get_instance_id(self):
        try:
            if self.instance_metadata:
                return self.instance_metadata.get("id")
        except Exception:
            logger.debug("get_instance_id error", exc_info=True)
        return None
