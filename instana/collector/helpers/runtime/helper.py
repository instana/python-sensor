import os
from ..base import BaseHelper
from instana.log import logger
from instana.util import DictionaryOfStan


class RuntimeHelper(BaseHelper):
    def collect_metrics(self, with_snapshot = False):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.python"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["metrics"] = self.collect_runtime_metrics()
            plugin_data["data"]["snapshot"] = self._collect_runtime_snapshot()
        except:
            logger.debug("_collect_runtime_snapshot: ", exc_info=True)
        return [plugin_data]

