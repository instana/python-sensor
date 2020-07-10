from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan, normalize_aws_lambda_arn


class AWSLambdaCollector(BaseCollector):
    def __init__(self, agent):
        super(AWSLambdaCollector, self).__init__(agent)
        logger.debug("Loading AWS Lambda Collector")
        self._fq_arn = None

    def collect_snapshot(self, event, context):
        self.snapshot_data = DictionaryOfStan()

        self.context = context
        self.event = event

        try:
            plugin_data = dict()
            plugin_data["name"] = "com.instana.plugin.aws.lambda"
            plugin_data["entityId"] = self.get_fq_arn()
            self.snapshot_data["plugins"] = [plugin_data]
        except:
            logger.debug("collect_snapshot error", exc_info=True)
        finally:
            return self.snapshot_data

    def prepare_payload(self):
        payload = DictionaryOfStan()
        payload["spans"] = None
        payload["metrics"] = None

        if not self.span_queue.empty():
            payload["spans"] = self.__queued_spans()

        if self.snapshot_data and self.snapshot_data_sent is False:
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

