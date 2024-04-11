# (c) Copyright IBM Corp. 2024

"""Module to handle the collection of containerized process metrics for EKS Pods on AWS Fargate"""

import os

from instana.collector.helpers.process import ProcessHelper
from instana.log import logger


def get_pod_name():
    podname = os.environ.get("HOSTNAME", "")

    if not podname:
        logger.warning("Failed to determine podname from EKS hostname.")
    return podname


class EKSFargateProcessHelper(ProcessHelper):
    """Helper class to extend the generic process helper class with the corresponding fargate attributes"""

    def collect_metrics(self, **kwargs):
        plugin_data = dict()
        try:
            plugin_data = super(EKSFargateProcessHelper, self).collect_metrics(**kwargs)
            plugin_data["data"]["containerType"] = "docker"

            if kwargs.get("with_snapshot"):
                plugin_data["data"]["com.instana.plugin.host.name"] = get_pod_name()
        except Exception:
            logger.debug("EKSFargateProcessHelper.collect_metrics: ", exc_info=True)
        return [plugin_data]
