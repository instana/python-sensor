import os
import pwd
import grp
from ..base import BaseHelper
from instana.log import logger
from instana.util import DictionaryOfStan, get_proc_cmdline, strip_secrets


class ProcessHelper(BaseHelper):
    def collect_metrics(self, with_snapshot = False):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.process"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["pid"] = int(os.getpid())
            env = dict()
            for key in os.environ:
                env[key] = os.environ[key]
            plugin_data["data"]["env"] = env
            plugin_data["data"]["exec"] = os.readlink("/proc/self/exe")

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
            except:
                logger.debug("euid/egid detection: ", exc_info=True)

            plugin_data["data"]["start"] = 1 # FIXME
            plugin_data["data"]["containerType"] = "docker"
            if self.collector.root_metadata is not None:
                plugin_data["data"]["container"] = self.collector.root_metadata.get("DockerId")
            # plugin_data["data"]["com.instana.plugin.host.pid"] = 1 # FIXME: the pid in the root namespace (very optional)
            if self.collector.task_metadata is not None:
                plugin_data["data"]["com.instana.plugin.host.name"] = self.collector.task_metadata.get("TaskArn")
        except:
            logger.debug("_collect_process_snapshot: ", exc_info=True)
        return [plugin_data]
