
from ..log import logger
from .base import BaseCollector
from ..util import DictionaryOfStan


class AWSFargateCollector(BaseCollector):
    def __init__(self, agent):
        super(AWSFargateCollector, self).__init__(agent)
        logger.debug("Loading AWS Fargate Collector")

    def collect_snapshot(self, event, context):
        self.snapshot_data = DictionaryOfStan()

        self.context = context
        self.event = event

        try:
            plugin_data = dict()
            plugin_data["name"] = "com.instana.plugin.aws.lambda"
            self.snapshot_data["plugins"] = [plugin_data]
        except:
            logger.debug("collect_snapshot error", exc_info=True)
        finally:
            return self.snapshot_data

