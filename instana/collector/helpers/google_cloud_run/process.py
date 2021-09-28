# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

from instana.collector.helpers.process import ProcessHelper
from instana.log import logger


class GCRProcessHelper(ProcessHelper):
    """ Helper class to extend the generic process helper class with the corresponding fargate attributes """

    def collect_metrics(self, with_snapshot=False):
        plugin_data = dict()
        try:
            plugin_data = super(GCRProcessHelper, self).collect_metrics(with_snapshot)
            plugin_data["data"]["containerType"] = "gcpCloudRunInstance"
            plugin_data["data"]["container"] = self.collector.get_instance_id()
            plugin_data["data"]["com.instana.plugin.host.name"] = "gcp:cloud-run:revision:{revision}".format(
                revision=self.collector.revision)
        except Exception:
            logger.debug("FargateProcessHelper.collect_metrics: ", exc_info=True)
        return [plugin_data]
