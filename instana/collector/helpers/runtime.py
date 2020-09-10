""" Collection helper for the Python runtime """
import os
import gc
import sys
import platform
import resource
import threading
from types import ModuleType
from pkg_resources import DistributionNotFound, get_distribution

from instana.log import logger
from instana.version import VERSION
from instana.util import DictionaryOfStan, determine_service_name

from .base import BaseHelper


class RuntimeHelper(BaseHelper):
    """ Helper class to collect snapshot and metrics for this Python runtime """
    def __init__(self, collector):
        super(RuntimeHelper, self).__init__(collector)
        self.previous = DictionaryOfStan()
        self.previous_rusage = resource.getrusage(resource.RUSAGE_SELF)

        if gc.isenabled():
            self.previous_gc_count = gc.get_count()
        else:
            self.previous_gc_count = None

    def collect_metrics(self, with_snapshot=False):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.python"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()

            if hasattr(self.collector.agent, "announce_data"):
                try:
                    plugin_data["data"]["pid"] = self.collector.agent.announce_data.pid
                except Exception:
                    plugin_data["data"]["pid"] = str(os.getpid())
            else:
                plugin_data["data"]["pid"] = str(os.getpid())

            self._collect_runtime_metrics(plugin_data, with_snapshot)

            if with_snapshot is True:
                self._collect_runtime_snapshot(plugin_data)
        except Exception:
            logger.debug("_collect_metrics: ", exc_info=True)
        return [plugin_data]

    def _collect_runtime_metrics(self, plugin_data, with_snapshot):
        """ Collect up and return the runtime metrics """
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            if gc.isenabled():
                self._collect_gc_metrics(plugin_data, with_snapshot)

            self._collect_thread_metrics(plugin_data, with_snapshot)

            value_diff = rusage.ru_utime - self.previous_rusage.ru_utime
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_utime", with_snapshot)

            value_diff = rusage.ru_stime - self.previous_rusage.ru_stime
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_stime", with_snapshot)

            self.apply_delta(rusage.ru_maxrss, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_maxrss", with_snapshot)
            self.apply_delta(rusage.ru_ixrss, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_ixrss", with_snapshot)
            self.apply_delta(rusage.ru_idrss, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_idrss", with_snapshot)
            self.apply_delta(rusage.ru_isrss, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_isrss", with_snapshot)

            value_diff = rusage.ru_minflt - self.previous_rusage.ru_minflt
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_minflt", with_snapshot)

            value_diff = rusage.ru_majflt - self.previous_rusage.ru_majflt
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_majflt", with_snapshot)

            value_diff = rusage.ru_nswap - self.previous_rusage.ru_nswap
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_nswap", with_snapshot)

            value_diff = rusage.ru_inblock - self.previous_rusage.ru_inblock
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_inblock", with_snapshot)

            value_diff = rusage.ru_oublock - self.previous_rusage.ru_oublock
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_oublock", with_snapshot)

            value_diff = rusage.ru_msgsnd - self.previous_rusage.ru_msgsnd
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_msgsnd", with_snapshot)

            value_diff = rusage.ru_msgrcv - self.previous_rusage.ru_msgrcv
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_msgrcv", with_snapshot)

            value_diff = rusage.ru_nsignals - self.previous_rusage.ru_nsignals
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_nsignals", with_snapshot)

            value_diff = rusage.ru_nvcsw - self.previous_rusage.ru_nvcsw
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_nvcsw", with_snapshot)

            value_diff = rusage.ru_nivcsw - self.previous_rusage.ru_nivcsw
            self.apply_delta(value_diff, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "ru_nivcsw", with_snapshot)
        except Exception:
            logger.debug("_collect_runtime_metrics", exc_info=True)
        finally:
            self.previous_rusage = rusage

    def _collect_gc_metrics(self, plugin_data, with_snapshot):
        try:
            gc_count = gc.get_count()
            gc_threshold = gc.get_threshold()

            self.apply_delta(gc_count[0], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "collect0", with_snapshot)
            self.apply_delta(gc_count[1], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "collect1", with_snapshot)
            self.apply_delta(gc_count[2], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "collect2", with_snapshot)

            self.apply_delta(gc_threshold[0], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "threshold0", with_snapshot)
            self.apply_delta(gc_threshold[1], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "threshold1", with_snapshot)
            self.apply_delta(gc_threshold[2], self.previous['data']['metrics']['gc'],
                             plugin_data['data']['metrics']['gc'], "threshold2", with_snapshot)
        except Exception:
            logger.debug("_collect_gc_metrics", exc_info=True)

    def _collect_thread_metrics(self, plugin_data, with_snapshot):
        try:
            threads = threading.enumerate()
            daemon_threads = [thread.daemon is True for thread in threads].count(True)
            self.apply_delta(daemon_threads, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "daemon_threads", with_snapshot)

            alive_threads = [thread.daemon is False for thread in threads].count(True)
            self.apply_delta(alive_threads, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "alive_threads", with_snapshot)

            dummy_threads = [isinstance(thread, threading._DummyThread) for thread in threads].count(True) # pylint: disable=protected-access
            self.apply_delta(dummy_threads, self.previous['data']['metrics'],
                             plugin_data['data']['metrics'], "dummy_threads", with_snapshot)
        except Exception:
            logger.debug("_collect_thread_metrics", exc_info=True)

    def _collect_runtime_snapshot(self,plugin_data):
        """ Gathers Python specific Snapshot information for this process """
        snapshot_payload = {}
        try:
            snapshot_payload['name'] = determine_service_name()
            snapshot_payload['version'] = sys.version
            snapshot_payload['f'] = platform.python_implementation() # flavor
            snapshot_payload['a'] = platform.architecture()[0] # architecture
            snapshot_payload['versions'] = self.gather_python_packages()
            snapshot_payload['iv'] = VERSION

            if 'AUTOWRAPT_BOOTSTRAP' in os.environ:
                snapshot_payload['m'] = 'Autowrapt'
            elif 'INSTANA_MAGIC' in os.environ:
                snapshot_payload['m'] = 'AutoTrace'
            else:
                snapshot_payload['m'] = 'Manual'

            try:
                from django.conf import settings # pylint: disable=import-outside-toplevel
                if hasattr(settings, 'MIDDLEWARE') and settings.MIDDLEWARE is not None:
                    snapshot_payload['djmw'] = settings.MIDDLEWARE
                elif hasattr(settings, 'MIDDLEWARE_CLASSES') and settings.MIDDLEWARE_CLASSES is not None:
                    snapshot_payload['djmw'] = settings.MIDDLEWARE_CLASSES
            except Exception:
                pass
        except Exception:
            logger.debug("collect_snapshot: ", exc_info=True)

        plugin_data['data']['snapshot'] = snapshot_payload

    def gather_python_packages(self):
        """ Collect up the list of modules in use """
        versions = dict()
        try:
            sys_packages = sys.modules.copy()

            for pkg_name in sys_packages:
                # Don't report submodules (e.g. django.x, django.y, django.z)
                # Skip modules that begin with underscore
                if ('.' in pkg_name) or pkg_name[0] == '_':
                    continue

                # Skip builtins
                if pkg_name in ["sys", "curses"]:
                    continue

                if sys_packages[pkg_name]:
                    try:
                        pkg_info = sys_packages[pkg_name].__dict__
                        if "__version__" in pkg_info:
                            if isinstance(pkg_info["__version__"], str):
                                versions[pkg_name] = pkg_info["__version__"]
                            else:
                                versions[pkg_name] = self.jsonable(pkg_info["__version__"])
                        elif "version" in pkg_info:
                            versions[pkg_name] = self.jsonable(pkg_info["version"])
                        else:
                            versions[pkg_name] = get_distribution(pkg_name).version
                    except DistributionNotFound:
                        pass
                    except Exception:
                        logger.debug("gather_python_packages: could not process module: %s", pkg_name)
            
            # Manually set our package version
            versions['instana'] = VERSION
        except Exception:
            logger.debug("gather_python_packages", exc_info=True)

        return versions

    def jsonable(self, value):
        try:
            if callable(value):
                try:
                    result = value()
                except Exception:
                    result = 'Unknown'
            elif isinstance(value, ModuleType):
                result = value
            else:
                result = value
            return str(result)
        except Exception:
            logger.debug("jsonable: ", exc_info=True)
