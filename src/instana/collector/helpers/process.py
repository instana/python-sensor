# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""Collection helper for the process"""

import grp
import os
import pwd

from instana.collector.helpers.base import BaseHelper
from instana.log import logger
from instana.util import DictionaryOfStan
from instana.util.runtime import get_proc_cmdline
from instana.util.secrets import contains_secret


class ProcessHelper(BaseHelper):
    """Helper class to collect metrics for this process"""

    def collect_metrics(self, **kwargs):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.process"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["pid"] = int(os.getpid())

            if kwargs.get("with_snapshot"):
                self._collect_process_snapshot(plugin_data)
        except Exception:
            logger.debug("ProcessHelper.collect_metrics: ", exc_info=True)
        return plugin_data

    def _collect_process_snapshot(self, plugin_data):
        try:
            env = dict()
            for key in os.environ:
                if contains_secret(
                    key,
                    self.collector.agent.options.secrets_matcher,
                    self.collector.agent.options.secrets_list,
                ):
                    env[key] = "<ignored>"
                else:
                    env[key] = os.environ[key]
            plugin_data["data"]["env"] = env
            if os.path.isfile("/proc/self/exe"):
                plugin_data["data"]["exec"] = os.readlink("/proc/self/exe")
            else:
                logger.debug("Can't access /proc/self/exe...")

            cmdline = get_proc_cmdline()
            if len(cmdline) > 1:
                # drop the exe
                cmdline.pop(0)
            plugin_data["data"]["args"] = cmdline
            try:
                euid = os.geteuid()
                egid = os.getegid()
                plugin_data["data"]["user"] = pwd.getpwuid(euid)
                plugin_data["data"]["group"] = grp.getgrgid(egid).gr_name
            except Exception:
                logger.debug("euid/egid detection: ", exc_info=True)

            plugin_data["data"]["start"] = self.collector.fetching_start_time

        except Exception:
            logger.debug("ProcessHelper._collect_process_snapshot: ", exc_info=True)
