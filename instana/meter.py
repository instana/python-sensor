import threading
import resource
import os
import gc as gc_
import sys
import copy
import time
from types import ModuleType
import instana
from .log import logger as log
from .agent_const import AGENT_DATA_URL


class Snapshot(object):
    name = None
    version = None
    rlimit_core = (0, 0)
    rlimit_cpu = (0, 0)
    rlimit_fsize = (0, 0)
    rlimit_data = (0, 0)
    rlimit_stack = (0, 0)
    rlimit_rss = (0, 0)
    rlimit_nproc = (0, 0)
    rlimit_nofile = (0, 0)
    rlimit_memlock = (0, 0)
    rlimit_as = (0, 0)
    versions = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_dict(self):
        kvs = dict()
        kvs['name'] = self.name
        kvs['version'] = self.version
        kvs['versions'] = self.versions
        return kvs


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


class EntityData(object):
    pid = 0
    snapshot = None
    metrics = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_dict(self):
        return self.__dict__


class Meter(object):
    SNAPSHOT_PERIOD = 600
    snapshot_countdown = 35
    sensor = None
    last_usage = None
    last_collect = None
    timer = None
    last_metrics = None

    def __init__(self, sensor):
        self.sensor = sensor

    def run(self):
        self.timer = threading.Thread(target=self.collect_and_report)
        self.timer.daemon = True
        self.timer.name = "Instana Metric Collection"
        self.timer.start()

    def collect_and_report(self):
        while 1:
            self.process()
            if (self.sensor.agent.is_timed_out()):
                log.warn("Host agent offline for >1 min.  Going to sit in a corner...")
                self.sensor.agent.reset()
                break
            time.sleep(1)

    def process(self):
        if self.sensor.agent.can_send():
            self.snapshot_countdown = self.snapshot_countdown - 1
            ss = None
            cm = self.collect_metrics()

            if self.snapshot_countdown < 1:
                self.snapshot_countdown = self.SNAPSHOT_PERIOD
                ss = self.collect_snapshot()
                md = copy.deepcopy(cm).delta_data(None)
            else:
                md = copy.deepcopy(cm).delta_data(self.last_metrics)

            ed = EntityData(pid=self.sensor.agent.from_.pid, snapshot=ss, metrics=md)
            url = self.sensor.agent.make_url(AGENT_DATA_URL)
            self.sensor.agent.request(url, "POST", ed)
            self.last_metrics = cm.__dict__

    def collect_snapshot(self):
        try:
            if instana.service_name:
                appname = instana.service_name
            elif "FLASK_APP" in os.environ:
                appname = os.environ["FLASK_APP"]
            elif "DJANGO_SETTINGS_MODULE" in os.environ:
                appname = os.environ["DJANGO_SETTINGS_MODULE"].split('.')[0]
            else:
                appname = os.path.basename(sys.argv[0])

            s = Snapshot(name=appname, version=sys.version)
            s.version = sys.version
            s.rlimit_core = resource.getrlimit(resource.RLIMIT_CORE)
            s.rlimit_cpu = resource.getrlimit(resource.RLIMIT_CPU)
            s.rlimit_fsize = resource.getrlimit(resource.RLIMIT_FSIZE)
            s.rlimit_data = resource.getrlimit(resource.RLIMIT_DATA)
            s.rlimit_stack = resource.getrlimit(resource.RLIMIT_STACK)
            s.rlimit_rss = resource.getrlimit(resource.RLIMIT_RSS)
            s.rlimit_nproc = resource.getrlimit(resource.RLIMIT_NPROC)
            s.rlimit_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
            s.rlimit_memlock = resource.getrlimit(resource.RLIMIT_MEMLOCK)
            s.rlimit_as = resource.getrlimit(resource.RLIMIT_AS)
            s.versions = self.collect_modules()

            return s
        except Exception as e:
            log.debug("collect_snapshot: ", str(e))

            return None

    def jsonable(self, value):
        try:
            if callable(value):
                result = value()
            elif type(value) is ModuleType:
                result = value
            else:
                result = value
            return str(result)
        except Exception as e:
            log.debug(e)

    def collect_modules(self):
        try:
            m = sys.modules
            r = {}
            for k in m:
                # Don't report submodules (e.g. django.x, django.y, django.z)
                if ('.' in k):
                    continue
                if m[k]:
                    try:
                        d = m[k].__dict__
                        if "version" in d and d["version"]:
                            r[k] = self.jsonable(d["version"])
                        elif "__version__" in d and d["__version__"]:
                            r[k] = self.jsonable(d["__version__"])
                        else:
                            r[k] = "builtin"
                    except Exception as e:
                        r[k] = "unknown"
                        log.debug("collect_modules: could not process module ", k, str(e))

            return r
        except Exception as e:
            log.debug("collect_modules: ", str(e))

            return None

    def collect_metrics(self):
        u = resource.getrusage(resource.RUSAGE_SELF)
        if gc_.isenabled():
            c = list(gc_.get_count())
            th = list(gc_.get_threshold())
            g = GC(collect0=c[0] if not self.last_collect else c[0] - self.last_collect[0],
                   collect1=c[1] if not self.last_collect else c[
                       1] - self.last_collect[1],
                   collect2=c[2] if not self.last_collect else c[
                       2] - self.last_collect[2],
                   threshold0=th[0],
                   threshold1=th[1],
                   threshold2=th[2])

        thr = threading.enumerate()
        daemon_threads = [tr.daemon is True for tr in thr].count(True)
        alive_threads = [tr.daemon is False for tr in thr].count(True)
        dummy_threads = [type(tr) is threading._DummyThread for tr in thr].count(True)

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
