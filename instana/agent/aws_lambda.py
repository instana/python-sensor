"""
The Instana agent (for AWS Lambda functions) that manages
monitoring state and reporting that data.
"""
import time
from ..log import logger
from ..util import to_json, package_version
from .base import BaseAgent
from ..collector.aws_lambda import AWSLambdaCollector
from ..options import AWSLambdaOptions


class AWSLambdaFrom(object):
    """ The source identifier for AWSLambdaAgent """
    hl = True
    cp = "aws"
    e = "qualifiedARN"

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class AWSLambdaAgent(BaseAgent):
    """ In-process agent for AWS Lambda """
    def __init__(self):
        super(AWSLambdaAgent, self).__init__()

        self.from_ = AWSLambdaFrom()
        self.collector = None
        self.options = AWSLambdaOptions()
        self.report_headers = None
        self._can_send = False

        # Update log level from what Options detected
        self.update_log_level()

        logger.info("Stan is on the AWS Lambda scene.  Starting Instana instrumentation version: %s", package_version())

        if self._validate_options():
            self._can_send = True
            self.collector = AWSLambdaCollector(self)
            self.collector.start()
        else:
            logger.warning("Required INSTANA_AGENT_KEY and/or INSTANA_ENDPOINT_URL environment variables not set.  "
                           "We will not be able monitor this function.")

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
        return {'hl': True, 'cp': 'aws', 'e': self.collector.get_fq_arn()}

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
                self.report_headers["X-Instana-Host"] = self.collector.get_fq_arn()
                self.report_headers["X-Instana-Key"] = self.options.agent_key

            self.report_headers["X-Instana-Time"] = str(round(time.time() * 1000))

            response = self.client.post(self.__data_bundle_url(),
                                        data=to_json(payload),
                                        headers=self.report_headers,
                                        timeout=self.options.timeout,
                                        verify=self.options.ssl_verify,
                                        proxies=self.options.endpoint_proxy)

            if 200 <= response.status_code < 300:
                logger.debug("report_data_payload: Instana responded with status code %s", response.status_code)
            else:
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
