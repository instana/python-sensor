import threading

from ...log import logger
from ..runtime import min_version, runtime_info
from ..profile import Profile
from ..profile import CallSite
from ..schedule import schedule, delay

if min_version(3, 4):
    import tracemalloc


class AllocationSampler(object):
    MAX_TRACEBACK_SIZE = 25 # number of frames
    MAX_MEMORY_OVERHEAD = 10 * 1e6 # 10MB
    MAX_PROFILED_ALLOCATIONS = 25

    def __init__(self, profiler):
        self.profiler = profiler
        self.ready = False
        self.top = None
        self.top_lock = threading.Lock()
        self.overhead_monitor = None

    def setup(self):
        if self.profiler.get_option('allocation_sampler_disabled'):
            return

        if not runtime_info.OS_LINUX and not runtime_info.OS_DARWIN:
            logger.debug('Allocation sampler is only supported on Linux and OS X.')
            return

        if not min_version(3, 4):
            logger.debug('Memory allocation profiling is available for Python 3.4 or higher')
            return

        self.ready = True

    def reset(self):
        self.top = CallSite('', '', 0)

    def start_sampler(self):
        logger.debug('Activating memory allocation sampler.')

        def start():
            tracemalloc.start(self.MAX_TRACEBACK_SIZE)
        self.profiler.run_in_main_thread(start)

        def monitor_overhead():
            if tracemalloc.is_tracing() and tracemalloc.get_tracemalloc_memory() > self.MAX_MEMORY_OVERHEAD:
                logger.debug('Allocation sampler memory overhead limit exceeded: %s bytes', tracemalloc.get_tracemalloc_memory())
                self.stop_sampler()

        if not self.profiler.get_option('disable_timers'):
            self.overhead_monitor = schedule(0.5, 0.5, monitor_overhead)

    def stop_sampler(self):
        logger.debug('Deactivating memory allocation sampler.')

        with self.top_lock:
            if self.overhead_monitor:
                self.overhead_monitor.cancel()
                self.overhead_monitor = None

            if tracemalloc.is_tracing():
                snapshot = tracemalloc.take_snapshot()
                logger.debug('Allocation sampler memory overhead %s bytes', tracemalloc.get_tracemalloc_memory())
                tracemalloc.stop()
                self.process_snapshot(snapshot)

    def build_profile(self, duration, timespan):
        with self.top_lock:
            self.top.normalize(duration)
            self.top.floor()

            profile = Profile(
                Profile.CATEGORY_MEMORY,
                Profile.TYPE_MEMORY_ALLOCATION_RATE,
                Profile.UNIT_BYTE,
                self.top.children.values(),
                duration,
                timespan
            )

            return profile

    def destroy(self):
        pass

    def process_snapshot(self, snapshot):
        stats = snapshot.statistics('traceback')

        for stat in stats[:self.MAX_PROFILED_ALLOCATIONS]:
            if stat.traceback:
                skip_stack = False
                for frame in stat.traceback:
                    if frame.filename and self.profiler.frame_cache.is_profiler_frame(frame.filename):
                        skip_stack = True
                        break
                if skip_stack:
                    continue

                current_node = self.top
                for frame in reversed(stat.traceback):
                    if frame.filename == '<unknown>':
                        continue

                    current_node = current_node.find_or_add_child('', frame.filename, frame.lineno)
                current_node.increment(stat.size, stat.count)
