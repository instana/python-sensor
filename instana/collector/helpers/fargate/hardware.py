""" Module to handle the reporting of the hardware plugin in AWS Fargate """
from ....log import logger
from ....util import DictionaryOfStan
from ..base import BaseHelper


class HardwareHelper(BaseHelper):
    """ This class acts as a helper to collect data for the hardware plugin """
    def collect_metrics(self, with_snapshot=False):
        """
        # This helper only sends snapshot data related to the INSTANA_ZONE environment variable
        @return: list
        """
        plugins = []
        if with_snapshot is False or self.collector.agent.options.zone is None:
            return plugins

        try:
            if self.collector.task_metadata is not None:
                plugin_data = dict()
                plugin_data["name"] = "com.instana.plugin.generic.hardware"
                try:
                    plugin_data["entityId"] = self.collector.task_metadata.get("TaskARN", None)
                    plugin_data["data"] = DictionaryOfStan()
                    plugin_data["data"]["availability-zone"] = self.collector.agent.options.zone
                except Exception:
                    logger.debug("HardwareHelper.collect_metrics: ", exc_info=True)
                finally:
                    plugins.append(plugin_data)
        except Exception:
            logger.debug("HardwareHelper.collect_metrics: ", exc_info=True)
        return plugins
