"""
Snapshot & metrics collection for AWS Lambda
"""
from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan, normalize_aws_lambda_arn


class AWSLambdaCollector(BaseCollector):
    """ Collector for AWS Lambda """
    def __init__(self, agent):
        super(AWSLambdaCollector, self).__init__(agent)
        logger.debug("Loading AWS Lambda Collector")
        self.context = None
        self.event = None
        self._fq_arn = None

        # How often to report data
        self.report_interval = 5

        self.snapshot_data = DictionaryOfStan()
        self.snapshot_data_sent = False

    def collect_snapshot(self, event, context):
        self.context = context
        self.event = event

        try:
            plugin_data = dict()
            plugin_data["name"] = "com.instana.plugin.aws.lambda"
            plugin_data["entityId"] = self.get_fq_arn()
            self.snapshot_data["plugins"] = [plugin_data]
        except Exception:
            logger.debug("collect_snapshot error", exc_info=True)
        return self.snapshot_data

    def should_send_snapshot_data(self):
        return self.snapshot_data and self.snapshot_data_sent is False

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = None
        payload["metrics"] = None

        if not self.span_queue.empty():
            payload["spans"] = self.queued_spans()

        if self.should_send_snapshot_data():
            payload["metrics"] = self.snapshot_data
            self.snapshot_data_sent = True

        return payload

    def get_fq_arn(self):
        if self._fq_arn is not None:
            return self._fq_arn

        if self.context is None:
            logger.debug("Attempt to get qualified ARN before the context object is available")
            return ''

        self._fq_arn = normalize_aws_lambda_arn(self.context)
        return self._fq_arn
