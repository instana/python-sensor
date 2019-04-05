import copy
import gc as gc_
import json
import os
import platform
import resource
import sys
import threading
from types import ModuleType

from pkg_resources import DistributionNotFound, get_distribution

from .log import logger
from .util import get_py_source, package_version, every


class Snapshot(object):
    name = None
    version = None
    f = None  # flavor: CPython, Jython, IronPython, PyPy
    a = None  # architecture: i386, x86, x86_64, AMD64
    versions = None
    djmw = []

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

    def to_dict(self):
        kvs = dict()
        kvs['name'] = self.name
        kvs['version'] = self.version
        kvs['f'] = self.f  # flavor
        kvs['a'] = self.a  # architecture
        kvs['versions'] = self.versions
        kvs['djmw'] = list(self.djmw)
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
    snapshot_countdown = 0

    # The agent that this instance belongs to
    agent = None

    last_usage = None
    last_collect = None
    last_metrics = None
    djmw = None
    thr = None

    # A True value signals the metric reporting thread to shutdown
    _shutdown = False

    def __init__(self, agent):
        self.agent = agent
        pass

    def run(self):
        """ Spawns the metric reporting thread """
        self.thr = threading.Thread(target=self.collect_and_report)
        self.thr.daemon = True
        self.thr.name = "Instana Metric Collection"
        self.thr.start()

    def reset(self):
        """" Reset the state as new """
        self.last_usage = None
        self.last_collect = None
        self.last_metrics = None
        self.snapshot_countdown = 0
        self.run()

    def collect_and_report(self):
        """
        Target function for the metric reporting thread.  This is a simple loop to
        collect and report entity data every 1 second.
        """
        logger.debug("Metric reporting thread is now alive")

        def metric_work():
            self.process()
            if self.agent.is_timed_out():
                logger.warn("Host agent offline for >1 min.  Going to sit in a corner...")
                self.agent.reset()
                return False
            return True

        every(1, metric_work, "Metrics Collection")

    def process(self):
        """ Collects, processes & reports metrics """
        if self.agent.machine.fsm.current is "wait4init":
            # Test the host agent if we're ready to send data
            if self.agent.is_agent_ready():
                self.agent.machine.fsm.ready()
            else:
                return

        if self.agent.can_send():
            self.snapshot_countdown = self.snapshot_countdown - 1
            ss = None
            cm = self.collect_metrics()

            if self.snapshot_countdown < 1:
                logger.debug("Sending process snapshot data")
                self.snapshot_countdown = self.SNAPSHOT_PERIOD
                ss = self.collect_snapshot()
                md = copy.deepcopy(cm).delta_data(None)
            else:
                md = copy.deepcopy(cm).delta_data(self.last_metrics)

            ed = EntityData(pid=self.agent.from_.pid, snapshot=ss, metrics=md)
            response = self.agent.report_data(ed)

            if response:
                if response.status_code is 200 and len(response.content) > 2:
                    # The host agent returned something indicating that is has a request for us that we
                    # need to process.
                    self.handle_agent_tasks(json.loads(response.content)[0])

                self.last_metrics = cm.__dict__

    def handle_agent_tasks(self, task):
        """
        When request(s) are received by the host agent, it is sent here
        for handling & processing.
        """
        logger.debug("Received agent request with messageId: %s" % task["messageId"])
        if "action" in task:
            if task["action"] == "python.source":
                payload = get_py_source(task["args"]["file"])
            else:
                message = "Unrecognized action: %s. An newer Instana package may be required " \
                          "for this. Current version: %s" % (task["action"], package_version())
                payload = {"error": message}
        else:
            payload = {"error": "Instana Python: No action specified in request."}

        self.agent.task_response(task["messageId"], payload)

    def collect_snapshot(self):
        """  Collects snapshot related information to this process and environment """
        try:
            if "INSTANA_SERVICE_NAME" in os.environ:
                appname = os.environ["INSTANA_SERVICE_NAME"]
            elif "FLASK_APP" in os.environ:
                appname = os.environ["FLASK_APP"]
            elif "DJANGO_SETTINGS_MODULE" in os.environ:
                appname = os.environ["DJANGO_SETTINGS_MODULE"].split('.')[0]
            elif os.path.basename(sys.argv[0]) == '' and sys.stdout.isatty():
                appname = "Interactive Console"
            else:
                if os.path.basename(sys.argv[0]) == '':
                    appname = os.path.basename(sys.executable)
                else:
                    appname = os.path.basename(sys.argv[0])

            s = Snapshot(name=appname, version=platform.version(),
                         f=platform.python_implementation(),
                         a=platform.architecture()[0],
                         djmw=self.djmw)
            s.version = sys.version
            s.versions = self.collect_modules()
        except Exception as e:
            logger.debug(e.message)
        else:
            return s

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
            logger.debug(e)

    def collect_modules(self):
        """ Collect up the list of modules in use """
        try:
            res = {}
            m = sys.modules
            for k in m:
                # Don't report submodules (e.g. django.x, django.y, django.z)
                # Skip modules that begin with underscore
                if ('.' in k) or k[0] == '_':
                    continue
                if m[k]:
                    try:
                        d = m[k].__dict__
                        if "version" in d and d["version"]:
                            res[k] = self.jsonable(d["version"])
                        elif "__version__" in d and d["__version__"]:
                            res[k] = self.jsonable(d["__version__"])
                        else:
                            res[k] = get_distribution(k).version
                    except DistributionNotFound:
                        pass
                    except Exception:
                        logger.debug("collect_modules: could not process module: %s" % k)

        except Exception:
            logger.debug("collect_modules", exc_info=True)
        else:
            return res

    def collect_metrics(self):
        """ Collect up and return various metrics """
        try:
            g = None
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
        except:
            logger.debug("collect_metrics", exc_info=True)
