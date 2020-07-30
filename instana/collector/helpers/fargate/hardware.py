from ....log import logger
from ....util import DictionaryOfStan
from ..base import BaseHelper


class HardwareHelper(BaseHelper):
    def collect_metrics(self, with_snapshot = False):
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
                except:
                    logger.debug("HardwareHelper.collect_metrics: ", exc_info=True)
                finally:
                    plugins.append(plugin_data)
        except:
            logger.debug("HardwareHelper.collect_metrics: ", exc_info=True)
        return plugins
