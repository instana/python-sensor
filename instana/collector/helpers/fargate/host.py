""" Module to help in collecting data for the host plugin in AWS Fargate """
from ....log import logger
from ..base import BaseHelper
from ....util import DictionaryOfStan


class HostHelper(BaseHelper):
    """ This class acts as a helper to collect data for the host plugin """
    def collect_metrics(self, with_snapshot=False):
        """
        # This helper only sends snapshot data related to the INSTANA_TAGS environment variable
        @return: list
        """
        plugins = []
        if with_snapshot is False or self.collector.agent.options.tags is None:
            return plugins

        plugin_data = dict()
        plugin_data["name"] = "com.instana.plugin.host"
        try:
            plugin_data["entityId"] = "h"
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["tags"] = self.collector.agent.options.tags
            plugins.append(plugin_data)
        except Exception:
            logger.debug("HostHelper.collect_metrics: ", exc_info=True)
        finally:
            plugins.append(plugin_data)
        return plugins
