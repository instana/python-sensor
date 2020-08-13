""" Collection helper for the Python runtime """
import os
import copy
import gc as gc_
import sys
import platform
import resource
import threading
from types import ModuleType
from pkg_resources import DistributionNotFound, get_distribution

from instana.log import logger
from instana.util import DictionaryOfStan, determine_service_name

from .base import BaseHelper


class RuntimeHelper(BaseHelper):
    """ Helper class to collect snapshot and metrics for this Python runtime """
    def __init__(self, collector):
        super(RuntimeHelper, self).__init__(collector)
        self.last_collect = None
        self.last_usage = None
        self.last_metrics = None

    def collect_metrics(self, with_snapshot=False):
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.python"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()
            plugin_data["data"]["pid"] = str(os.getpid())

            snapshot_payload = None
            metrics_payload = self.gather_metrics()

            if with_snapshot is True:
                snapshot_payload = self.gather_snapshot()
                metrics_payload = copy.deepcopy(metrics_payload).delta_data(None)
                plugin_data["data"]["snapshot"] = snapshot_payload
            else:
                metrics_payload = copy.deepcopy(metrics_payload).delta_data(self.last_metrics)

            plugin_data["data"]["metrics"] = metrics_payload

            self.last_metrics = metrics_payload
            #logger.debug(to_pretty_json(plugin_data))
        except Exception:
            logger.debug("_collect_runtime_snapshot: ", exc_info=True)
        return [plugin_data]

    def gather_metrics(self):
        """ Collect up and return various metrics """
        try:
            g = None
            u = resource.getrusage(resource.RUSAGE_SELF)
            if gc_.isenabled():
                c = list(gc_.get_count())
                th = list(gc_.get_threshold())
                g = GC(collect0=c[0] if not self.last_collect else c[0] - self.last_collect[0],
                       collect1=c[1] if not self.last_collect else c[1] - self.last_collect[1],
                       collect2=c[2] if not self.last_collect else c[2] - self.last_collect[2],
                       threshold0=th[0],
                       threshold1=th[1],
                       threshold2=th[2])

            thr = threading.enumerate()
            daemon_threads = [tr.daemon is True for tr in thr].count(True)
            alive_threads = [tr.daemon is False for tr in thr].count(True)
            dummy_threads = [isinstance(tr, threading._DummyThread) for tr in thr].count(True) # pylint: disable=protected-access

            m = Metrics(ru_utime=u[0] if not self.last_usage else u[0] - self.last_usage[0],
                        ru_stime=u[1] if not self.last_usage else u[1] - self.last_usage[1],
                        ru_maxrss=u[2],
                        ru_ixrss=u[3],
                        ru_idrss=u[4],
                        ru_isrss=u[5],
                        ru_minflt=u[6] if not self.last_usage else u[6] - self.last_usage[6],
                        ru_majflt=u[7] if not self.last_usage else u[7] - self.last_usage[7],
                        ru_nswap=u[8] if not self.last_usage else u[8] - self.last_usage[8],
                        ru_inblock=u[9] if not self.last_usage else u[9] - self.last_usage[9],
                        ru_oublock=u[10] if not self.last_usage else u[10] - self.last_usage[10],
                        ru_msgsnd=u[11] if not self.last_usage else u[11] - self.last_usage[11],
                        ru_msgrcv=u[12] if not self.last_usage else u[12] - self.last_usage[12],
                        ru_nsignals=u[13] if not self.last_usage else u[13] - self.last_usage[13],
                        ru_nvcs=u[14] if not self.last_usage else u[14] - self.last_usage[14],
                        ru_nivcsw=u[15] if not self.last_usage else u[15] - self.last_usage[15],
                        alive_threads=alive_threads,
                        dummy_threads=dummy_threads,
                        daemon_threads=daemon_threads,
                        gc=g)

            self.last_usage = u
            if gc_.isenabled():
                self.last_collect = c

            return m
        except Exception:
            logger.debug("collect_metrics", exc_info=True)

    def gather_snapshot(self):
        """ Gathers Python specific Snapshot information for this process """
        snapshot_payload = {}
        try:
            snapshot_payload['name'] = determine_service_name()
            snapshot_payload['version'] = sys.version
            snapshot_payload['f'] = platform.python_implementation() # flavor
            snapshot_payload['a'] = platform.architecture()[0] # architecture
            snapshot_payload['versions'] = self.gather_python_packages()
            #snapshot_payload['djmw'] = None # FIXME: django middleware reporting
        except Exception:
            logger.debug("collect_snapshot: ", exc_info=True)
        return snapshot_payload

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
                if sys_packages[pkg_name]:
                    try:
                        pkg_info = sys_packages[pkg_name].__dict__
                        if "version" in pkg_info:
                            versions[pkg_name] = self.jsonable(pkg_info["version"])
                        elif "__version__" in pkg_info:
                            if isinstance(pkg_info["__version__"], str):
                                versions[pkg_name] = pkg_info["__version__"]
                            else:
                                versions[pkg_name] = self.jsonable(pkg_info["__version__"])
                        else:
                            versions[pkg_name] = get_distribution(pkg_name).version
                    except DistributionNotFound:
                        pass
                    except Exception:
                        logger.debug("gather_python_packages: could not process module: %s", pkg_name)

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

class GC(object):
    collect0 = 0
    collect1 = 0
    collect2 = 0
    threshold0 = 0
    threshold1 = 0
    threshold2 = 0

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_dict(self):
        return self.__dict__


class Metrics(object):
    ru_utime = .0
    ru_stime = .0
    ru_maxrss = 0
    ru_ixrss = 0
    ru_idrss = 0
    ru_isrss = 0
    ru_minflt = 0
    ru_majflt = 0
    ru_nswap = 0
    ru_inblock = 0
    ru_oublock = 0
    ru_msgsnd = 0
    ru_msgrcv = 0
    ru_nsignals = 0
    ru_nvcs = 0
    ru_nivcsw = 0
    dummy_threads = 0
    alive_threads = 0
    daemon_threads = 0
    gc = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def delta_data(self, delta):
        data = self.__dict__
        if delta is None:
            return data

        unchanged_items = set(data.items()) & set(delta.items())
        for x in unchanged_items:
            data.pop(x[0])

        return data

    def to_dict(self):
        return self.__dict__
