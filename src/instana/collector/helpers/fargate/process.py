# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.collector.helpers.process import ProcessHelper
from instana.log import logger


class FargateProcessHelper(ProcessHelper):
    """ Helper class to extend the generic process helper class with the corresponding fargate attributes """

    def collect_metrics(self, **kwargs):
        plugin_data = dict()
        try:
            plugin_data = super(FargateProcessHelper, self).collect_metrics(**kwargs)
            plugin_data["data"]["containerType"] = "docker"
            if self.collector.root_metadata is not None:
                plugin_data["data"]["container"] = self.collector.root_metadata.get("DockerId")

            if kwargs.get("with_snapshot"):
                if self.collector.task_metadata is not None:
                    plugin_data["data"]["com.instana.plugin.host.name"] = self.collector.task_metadata.get("TaskArn")
        except Exception:
            logger.debug("FargateProcessHelper.collect_metrics: ", exc_info=True)
        return [plugin_data]
