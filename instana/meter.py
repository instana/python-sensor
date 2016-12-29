import threading as t
import thread
import instana.log as l
import resource
import os

class Snapshot(object):
    name = None
    rlimit_core=(0, 0)
    rlimit_cpu=(0, 0)
    rlimit_fsize=(0, 0)
    rlimit_data=(0, 0)
    rlimit_stack=(0, 0)
    rlimit_rss=(0, 0)
    rlimit_nproc=(0, 0)
    rlimit_nofile=(0, 0)
    rlimit_memlock=(0, 0)
    rlimit_as=(0, 0)

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

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
    ru_nsignals	= 0
    ru_nvcs = 0
    ru_nivcsw = 0

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class EntityData(object):
    pid = 0
    snapshot = None
    metrics = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class Meter(object):
    SNAPSHOT_PERIOD = 600
    snapshot_countdown = 1
    sensor = None
    last_usage = None

    def __init__(self, sensor):
        self.sensor = sensor
        self.tick()

    def tick(self):
        t.Timer(1, self.process).start()

    def process(self):
        if self.sensor.agent.can_send():
            self.snapshot_countdown = self.snapshot_countdown - 1
            s = None
            if self.snapshot_countdown == 0:
                self.snapshot_countdown = self.SNAPSHOT_PERIOD
                s = self.collect_snapshot()

            m = self.collect_metrics()
            d = EntityData(pid=os.getpid(), snapshot=s, metrics=m)

            thread.start_new_thread(self.sensor.agent.request,
                                    (self.sensor.agent.make_url(self.sensor.agent.AGENT_DATA_URL), "POST", d))

        self.tick()

    def collect_snapshot(self):
        s = Snapshot(name=self.sensor.service_name,
                     rlimit_core=resource.getrlimit(resource.RLIMIT_CORE),
                     rlimit_cpu=resource.getrlimit(resource.RLIMIT_CPU),
                     rlimit_fsize=resource.getrlimit(resource.RLIMIT_FSIZE),
                     rlimit_data=resource.getrlimit(resource.RLIMIT_DATA),
                     rlimit_stack=resource.getrlimit(resource.RLIMIT_STACK),
                     rlimit_rss=resource.getrlimit(resource.RLIMIT_RSS),
                     rlimit_nproc=resource.getrlimit(resource.RLIMIT_NPROC),
                     rlimit_nofile=resource.getrlimit(resource.RLIMIT_NOFILE),
                     rlimit_memlock=resource.getrlimit(resource.RLIMIT_MEMLOCK),
                     rlimit_as=resource.getrlimit(resource.RLIMIT_AS))

        return s

    def collect_metrics(self):
        u = resource.getrusage(resource.RUSAGE_SELF)
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
                    ru_nivcsw=u[15] if not self.last_usage else u[15] - self.last_usage[15])

        self.last_usage = u

        return m
