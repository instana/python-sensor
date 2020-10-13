import sys
import threading
import signal

from ...log import logger
from ..runtime import runtime_info
from ..profile import Profile
from ..profile import CallSite

if runtime_info.GEVENT:
    import gevent


class BlockSampler(object):
    SAMPLING_RATE = 0.05
    MAX_TRACEBACK_SIZE = 25 # number of frames

    def __init__(self, profiler):
        self.profiler = profiler
        self.ready = False
        self.top = None
        self.top_lock = threading.Lock()
        self.prev_signal_handler = None
        self.sampler_active = False

    def setup(self):
        if self.profiler.get_option('block_sampler_disabled'):
            return

        if not runtime_info.OS_LINUX and not runtime_info.OS_DARWIN:
            logger.debug('CPU profiler is only supported on Linux and OS X.')
            return

        sample_time = self.SAMPLING_RATE * 1000

        main_thread_id = None
        if runtime_info.GEVENT:
            main_thread_id = gevent._threading.get_ident()
        else:
            main_thread_id = threading.current_thread().ident

        def _sample(signum, signal_frame):
            if self.sampler_active:
                return
            self.sampler_active = True

            with self.top_lock:
                try:
                    self.process_sample(signal_frame, sample_time, main_thread_id)
                    signal_frame = None
                except Exception:
                    logger.error('Error processing sample', exc_info=True)

            self.sampler_active = False

        self.prev_signal_handler = signal.signal(signal.SIGALRM, _sample)

        self.ready = True

    def destroy(self):
        if not self.ready:
            return

        signal.signal(signal.SIGALRM, self.prev_signal_handler)

    def reset(self):
        self.top = CallSite('', '', 0)

    def start_sampler(self):
        logger.debug('Activating block sampler.')

        signal.setitimer(signal.ITIMER_REAL, self.SAMPLING_RATE, self.SAMPLING_RATE)

    def stop_sampler(self):
        signal.setitimer(signal.ITIMER_REAL, 0)

        logger.debug('Deactivating block sampler.')

    def build_profile(self, duration, timespan):
        with self.top_lock:
            self.top.normalize(duration)
            self.top.floor()

            profile = Profile(
                Profile.CATEGORY_TIME,
                Profile.TYPE_BLOCKING_CALLS,
                Profile.UNIT_MILLISECOND,
                self.top.children.values(),
                duration,
                timespan
            )

            return profile

    def process_sample(self, signal_frame, sample_time, main_thread_id):
        if self.top:
            current_frames = sys._current_frames()
            items = current_frames.items()
            for thread_id, thread_frame in items:
                if thread_id == main_thread_id:
                    thread_frame = signal_frame

                stack = self.recover_stack(thread_frame)
                if stack:
                    current_node = self.top
                    for func_name, filename, lineno in reversed(stack):
                        current_node = current_node.find_or_add_child(func_name, filename, lineno)
                    current_node.increment(sample_time, 1)

                thread_id, thread_frame, stack = None, None, None

            items = None
            current_frames = None


    def recover_stack(self, thread_frame):
        stack = []

        depth = 0
        while thread_frame is not None and depth <= self.MAX_TRACEBACK_SIZE:
            if thread_frame.f_code and thread_frame.f_code.co_name and thread_frame.f_code.co_filename:
                func_name = thread_frame.f_code.co_name
                filename = thread_frame.f_code.co_filename
                lineno = thread_frame.f_lineno

                if filename and self.profiler.frame_cache.is_profiler_frame(filename):
                    return None

                stack.append((func_name, filename, lineno))

                thread_frame = thread_frame.f_back

            depth += 1

        if len(stack) == 0:
            return None
        else:
            return stack
