# (c) Copyright IBM Corp. 2023

"""
The Instana agent (for AWS EKS Fargate) that manages
monitoring state and reporting that data.
"""
import os
import time
from instana.options import EKSFargateOptions
from instana.collector.aws_eks_fargate import EKSFargateCollector
from instana.collector.helpers.eks.process import get_pod_name
from instana.log import logger
from instana.util import to_json
from instana.agent.base import BaseAgent
from instana.version import VERSION


class EKSFargateAgent(BaseAgent):
    """ In-process agent for AWS Fargate """
    def __init__(self):
        super(EKSFargateAgent, self).__init__()

        self.options = EKSFargateOptions()
        self.collector = None
        self.report_headers = None
        self._can_send = False
        self.podname = get_pod_name()

        # Update log level (if INSTANA_LOG_LEVEL was set)
        self.update_log_level()

        logger.info("Stan is on the EKS Pod on AWS Fargate scene.  Starting Instana instrumentation version: %s", VERSION)

        if self._validate_options():
            self._can_send = True
            self.collector = EKSFargateCollector(self)
            self.collector.start()
        else:
            logger.warning("Required INSTANA_AGENT_KEY and/or INSTANA_ENDPOINT_URL environment variables not set.  "
                           "We will not be able to monitor this Pod.")

    def can_send(self):
        """
        Are we in a state where we can send data?
        @return: Boolean
        """
        return self._can_send

    def get_from_structure(self):
        """
        Retrieves the From data that is reported alongside monitoring data.
        @return: dict()
        """

        return {'hl': True, 'cp': 'k8s', 'e': self.podname}

    def report_data_payload(self, payload):
        """
        Used to report metrics and span data to the endpoint URL in self.options.endpoint_url
        """
        response = None
        try:
            if self.report_headers is None:
                # Prepare request headers
                self.report_headers = dict()
                self.report_headers["Content-Type"] = "application/json"
                self.report_headers["X-Instana-Host"] = self.podname
                self.report_headers["X-Instana-Key"] = self.options.agent_key

            response = self.client.post(self.__data_bundle_url(),
                                        data=to_json(payload),
                                        headers=self.report_headers,
                                        timeout=self.options.timeout,
                                        verify=self.options.ssl_verify,
                                        proxies=self.options.endpoint_proxy)

            if not 200 <= response.status_code < 300:
                logger.info("report_data_payload: Instana responded with status code %s", response.status_code)
        except Exception as exc:
            logger.debug("report_data_payload: connection error (%s)", type(exc))
        return response

    def _validate_options(self):
        """
        Validate that the options used by this Agent are valid.  e.g. can we report data?
        """
        return self.options.endpoint_url is not None and self.options.agent_key is not None

    def __data_bundle_url(self):
        """
        URL for posting metrics to the host agent.  Only valid when announced.
        """
        return "%s/bundle" % self.options.endpoint_url
