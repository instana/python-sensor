# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

""" Collection helper for the process """
import os
import pwd
import grp
from instana.log import logger
from instana.util import DictionaryOfStan
from instana.util.runtime import get_proc_cmdline
from instana.util.secrets import contains_secret
from .base import BaseHelper


class ProcessHelper(BaseHelper):
    """ Helper class to collect metrics for this process """
    def collect_metrics(self, with_snapshot=False):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.process"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["pid"] = int(os.getpid())
            plugin_data["data"]["containerType"] = "docker"
            if self.collector.root_metadata is not None:
                plugin_data["data"]["container"] = self.collector.root_metadata.get("DockerId")

            if with_snapshot:
                self._collect_process_snapshot(plugin_data)
        except Exception:
            logger.debug("ProcessHelper.collect_metrics: ", exc_info=True)
        return [plugin_data]

    def _collect_process_snapshot(self, plugin_data):
        try:
            env = dict()
            for key in os.environ:
                if contains_secret(key,
                                   self.collector.agent.options.secrets_matcher,
                                   self.collector.agent.options.secrets_list):
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

            plugin_data["data"]["start"] = 1 # FIXME: process start time reporting
            if self.collector.task_metadata is not None:
                plugin_data["data"]["com.instana.plugin.host.name"] = self.collector.task_metadata.get("TaskArn")
        except Exception:
            logger.debug("ProcessHelper._collect_process_snapshot: ", exc_info=True)
