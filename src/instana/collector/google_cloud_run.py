# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

"""
Google Cloud Run Collector: Manages the periodic collection of metrics & snapshot data
"""

import os
from time import time

import requests

from instana.collector.base import BaseCollector
from instana.collector.helpers.google_cloud_run.instance_entity import (
    InstanceEntityHelper,
)
from instana.collector.helpers.google_cloud_run.process import GCRProcessHelper
from instana.collector.utils import format_span
from instana.log import logger
from instana.util import DictionaryOfStan, validate_url


class GCRCollector(BaseCollector):
    """Collector for Google Cloud Run"""

    def __init__(self, agent, service, configuration, revision):
        super(GCRCollector, self).__init__(agent)
        logger.debug("Loading Google Cloud Run Collector")

        # Indicates if this Collector has all requirements to run successfully
        self.ready_to_start = True

        self.revision = revision
        self.service = service
        self.configuration = configuration
        # Prepare the URLS that we will collect data from
        self._gcr_md_uri = os.environ.get(
            "GOOGLE_CLOUD_RUN_METADATA_ENDPOINT", "http://metadata.google.internal"
        )

        if self._gcr_md_uri == "" or validate_url(self._gcr_md_uri) is False:
            logger.warning(
                "GCRCollector: GOOGLE_CLOUD_RUN_METADATA_ENDPOINT not in environment or invalid URL.  "
                "Instana will not be able to monitor this environment"
            )
            self.ready_to_start = False

        self._gcr_md_project_uri = (
            self._gcr_md_uri + "/computeMetadata/v1/project/?recursive=true"
        )
        self._gcr_md_instance_uri = (
            self._gcr_md_uri + "/computeMetadata/v1/instance/?recursive=true"
        )

        # Timestamp in seconds of the last time we fetched all GCR metadata
        self.__last_gcr_md_full_fetch = 0

        # How often to do a full fetch of GCR metadata
        self.__gcr_md_full_fetch_interval = 300

        # HTTP client with keep-alive
        self._http_client = requests.Session()

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
            logger.warning(
                "Google Cloud Run Collector is missing requirements and cannot monitor this environment."
            )
            return

        super(GCRCollector, self).start()

    def __get_project_instance_metadata(self):
        """
        Get the latest data from the service revision instance entity metadata and store in the class
        @return: Boolean
        """
        try:
            # Refetch the GCR snapshot data
            self.__last_gcr_md_full_fetch = int(time())
            headers = {"Metadata-Flavor": "Google"}
            # Response from the last call to
            # ${GOOGLE_CLOUD_RUN_METADATA_ENDPOINT}/computeMetadata/v1/project/?recursive=true
            self.project_metadata = self._http_client.get(
                self._gcr_md_project_uri, timeout=1, headers=headers
            ).json()

            # Response from the last call to
            # ${GOOGLE_CLOUD_RUN_METADATA_ENDPOINT}/computeMetadata/v1/instance/?recursive=true
            self.instance_metadata = self._http_client.get(
                self._gcr_md_instance_uri, timeout=1, headers=headers
            ).json()
        except Exception:
            logger.debug(
                "GoogleCloudRunCollector.get_project_instance_metadata", exc_info=True
            )

    def should_send_snapshot_data(self):
        return int(time()) - self.snapshot_data_last_sent > self.snapshot_data_interval

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = []
        payload["metrics"]["plugins"] = []

        try:
            if not self.span_queue.empty():
                payload["spans"] = format_span(self.queued_spans())

            self.fetching_start_time = int(time())
            delta = self.fetching_start_time - self.__last_gcr_md_full_fetch
            if delta < self.__gcr_md_full_fetch_interval:
                return payload

            with_snapshot = self.should_send_snapshot_data()

            # Fetch the latest metrics
            self.__get_project_instance_metadata()
            if self.instance_metadata is None and self.project_metadata is None:
                return payload

            plugins = []
            for helper in self.helpers:
                plugins.extend(
                    helper.collect_metrics(
                        with_snapshot=with_snapshot,
                        instance_metadata=self.instance_metadata,
                        project_metadata=self.project_metadata,
                    )
                )

            payload["metrics"]["plugins"] = plugins

            if with_snapshot:
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
