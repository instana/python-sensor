# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021

""" Module to assist in the data collection about the google cloud run service revision instance entity """
import os

from ....log import logger
from instana.collector.helpers.base import BaseHelper
from ....util import DictionaryOfStan


class InstanceEntityHelper(BaseHelper):
    """ This class helps in collecting data about the google cloud run service revision instance entity """

    def collect_metrics(self, **kwargs):
        """
        Collect and return metrics data (and optionally snapshot data) for this task
        @return: list - with one plugin entity
        """
        plugins = []
        plugin_data = dict()
        try:
            if self.collector.project_metadata and self.collector.instance_metadata:
                try:

                    plugin_data["name"] = "com.instana.plugin.gcp.run.revision.instance"
                    plugin_data["entityId"] = self.collector.instance_metadata.get("id")
                    plugin_data["data"] = DictionaryOfStan()
                    plugin_data["data"]["runtime"] = "python"
                    plugin_data["data"]["region"] = self.collector.instance_metadata.get("region").split("/")[-1]
                    plugin_data["data"]["service"] = self.collector.service
                    plugin_data["data"]["configuration"] = self.collector.configuration
                    plugin_data["data"]["revision"] = self.collector.revision
                    plugin_data["data"]["instanceId"] = plugin_data["entityId"]
                    plugin_data["data"]["port"] = os.getenv("PORT", "")
                    plugin_data["data"]["numericProjectId"] = self.collector.project_metadata.get("numericProjectId")
                    plugin_data["data"]["projectId"] = self.collector.project_metadata.get("projectId")

                except Exception:
                    logger.debug("collect_service_revision_entity_metrics: ", exc_info=True)
                finally:
                    plugins.append(plugin_data)
        except Exception:
            logger.debug("collect_service_revision_entity_metrics: ", exc_info=True)
        return plugins
