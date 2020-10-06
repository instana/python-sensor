import threading
import os
import signal
import atexit
import platform

from ..log import logger
from .runtime import min_version, runtime_info, register_signal
from .frame_cache import FrameCache
from .sampler_scheduler import SamplerScheduler, SamplerConfig
from .samplers.cpu_sampler import CPUSampler
from .samplers.allocation_sampler import AllocationSampler
from .samplers.block_sampler import BlockSampler


class Profiler(object):

    def __init__(self, agent):
        self.agent = agent

        self.profiler_started = False
        self.profiler_destroyed = False

        self.sampler_active = False

        self.main_thread_func = None

        self.frame_cache = FrameCache(self)

        config = SamplerConfig()
        config.log_prefix = 'CPU sampler'
        config.max_profile_duration = 20
        config.max_span_duration = 5
        config.max_span_count = 30
        config.span_interval = 20
        config.report_interval = 120
        self.cpu_sampler_scheduler = SamplerScheduler(self, CPUSampler(self), config)

        config = SamplerConfig()
        config.log_prefix = 'Allocation sampler'
        config.max_profile_duration = 20
        config.max_span_duration = 5
        config.max_span_count = 30
        config.span_interval = 20
        config.report_interval = 120
        self.allocation_sampler_scheduler = SamplerScheduler(self, AllocationSampler(self), config)

        config = SamplerConfig()
        config.log_prefix = 'Block sampler'
        config.max_profile_duration = 20
        config.max_span_duration = 5
        config.max_span_count = 30
        config.span_interval = 20
        config.report_interval = 120
        self.block_sampler_scheduler = SamplerScheduler(self, BlockSampler(self), config)

        self.options = None

    def get_option(self, name, default_val=None):
        if name not in self.options:
            return default_val
        else:
            return self.options[name]

    def start(self, **kwargs):
        if self.profiler_started:
            return

        try:
            if not min_version(2, 7) and not min_version(3, 4):
                raise Exception('Supported Python versions 2.6 or higher and 3.4 or higher')

            if platform.python_implementation() != 'CPython':
                raise Exception('Supported Python interpreter is CPython')

            if self.profiler_destroyed:
                logger.warning('Destroyed profiler cannot be started')
                return

            self.options = kwargs

            self.frame_cache.start()

            self.cpu_sampler_scheduler.setup()
            self.allocation_sampler_scheduler.setup()
            self.block_sampler_scheduler.setup()

            # execute main_thread_func in main thread on signal
            def _signal_handler(signum, frame):
                if(self.main_thread_func):
                    func = self.main_thread_func
                    self.main_thread_func = None
                    try:
                        func()
                    except Exception:
                        logger.error('Error in signal handler function', exc_info=True)

                    return True

            if not runtime_info.OS_WIN:
                register_signal(signal.SIGUSR2, _signal_handler)

            self.cpu_sampler_scheduler.start()
            self.allocation_sampler_scheduler.start()
            self.block_sampler_scheduler.start()

            self.profiler_started = True
            logger.debug('Profiler started')
        except Exception:
            logger.error('Error starting profiler', exc_info=True)

    def destroy(self):
        if not self.profiler_started:
            logger.warning('Profiler has not been started')
            return

        if self.profiler_destroyed:
            return

        self.frame_cache.stop()
        self.cpu_sampler_scheduler.stop()
        self.allocation_sampler_scheduler.stop()
        self.block_sampler_scheduler.stop()

        self.cpu_sampler_scheduler.destroy()
        self.allocation_sampler_scheduler.destroy()
        self.block_sampler_scheduler.destroy()

        self.profiler_destroyed = True
        logger.debug('Profiler destroyed')

    def run_in_thread(self, func):
        def func_wrapper():
            try:
                func()
            except Exception:
                logger.error('Error in thread function', exc_info=True)

        t = threading.Thread(target=func_wrapper)
        t.start()
        return t

    def run_in_main_thread(self, func):
        if self.main_thread_func:
            return False

        self.main_thread_func = func
        os.kill(os.getpid(), signal.SIGUSR2)

        return True
