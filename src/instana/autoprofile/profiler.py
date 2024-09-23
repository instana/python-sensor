# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import platform
import signal
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

from instana.autoprofile.frame_cache import FrameCache
from instana.autoprofile.runtime import RuntimeInfo, min_version, register_signal
from instana.autoprofile.sampler_scheduler import SamplerConfig, SamplerScheduler
from instana.autoprofile.samplers.allocation_sampler import AllocationSampler
from instana.autoprofile.samplers.block_sampler import BlockSampler
from instana.autoprofile.samplers.cpu_sampler import CPUSampler
from instana.log import logger

if TYPE_CHECKING:
    from types import FrameType
    from instana.agent.host import HostAgent


class Profiler(object):
    def __init__(self, agent: "HostAgent") -> None:
        self.agent = agent
        self.profiler_started = False
        self.profiler_destroyed = False
        self.sampler_active = False
        self.main_thread_func = None
        self.frame_cache = FrameCache(self)
        self.options = None
        self.cpu_sampler_scheduler = self._create_sampler_scheduler(
            CPUSampler(self), "CPU sampler", 20, 5, 30, 20, 120
        )
        self.allocation_sampler_scheduler = self._create_sampler_scheduler(
            AllocationSampler(self), "Allocation sampler", 20, 5, 30, 20, 120
        )
        self.block_sampler_scheduler = self._create_sampler_scheduler(
            BlockSampler(self), "Block sampler", 20, 5, 30, 20, 120
        )

    def get_option(
        self, name: str, default_val: Optional[object] = None
    ) -> Optional[object]:
        if name not in self.options:
            return default_val
        else:
            return self.options[name]

    def start(self, **kwargs: Dict[str, Any]) -> None:
        if self.profiler_started:
            return

        try:
            if not min_version(3, 8):
                raise Exception("Supported Python versions 3.8 or higher.")

            if platform.python_implementation() != "CPython":
                raise Exception("Supported Python interpreter is CPython.")

            if self.profiler_destroyed:
                logger.warning("Destroyed profiler cannot be started.")
                return

            self.options = kwargs
            self.frame_cache.start()
            self.cpu_sampler_scheduler.setup()
            self.allocation_sampler_scheduler.setup()
            self.block_sampler_scheduler.setup()

            # execute main_thread_func in main thread on signal
            def _signal_handler(signum: signal.Signals, frame: "FrameType") -> bool:
                if self.main_thread_func:
                    func = self.main_thread_func
                    self.main_thread_func = None
                    try:
                        func()
                    except Exception:
                        logger.error("Error in signal handler function", exc_info=True)

                    return True

            if not RuntimeInfo.OS_WIN:
                register_signal(signal.SIGUSR2, _signal_handler)

            self.cpu_sampler_scheduler.start()
            self.allocation_sampler_scheduler.start()
            self.block_sampler_scheduler.start()

            self.profiler_started = True
            logger.debug("Profiler started.")
        except Exception:
            logger.error("Error starting profiler", exc_info=True)

    def destroy(self) -> None:
        if not self.profiler_started:
            logger.warning("Profiler has not been started.")
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
        logger.debug("Profiler destroyed.")

    def run_in_thread(self, func: Callable[..., object]) -> threading.Thread:
        def func_wrapper() -> None:
            try:
                func()
            except Exception:
                logger.error("Error in thread function", exc_info=True)

        t = threading.Thread(target=func_wrapper)
        t.start()
        return t

    def run_in_main_thread(self, func: Callable[..., object]) -> bool:
        if self.main_thread_func:
            return False

        self.main_thread_func = func
        os.kill(os.getpid(), signal.SIGUSR2)

        return True

    def _create_sampler_scheduler(
        self,
        sampler: Union["AllocationSampler", "BlockSampler", "CPUSampler"],
        log_prefix: str,
        max_profile_duration: int,
        max_span_duration: int,
        max_span_count: int,
        span_interval: int,
        report_interval: int,
    ) -> SamplerScheduler:
        config = SamplerConfig()
        config.log_prefix = log_prefix
        config.max_profile_duration = max_profile_duration
        config.max_span_duration = max_span_duration
        config.max_span_count = max_span_count
        config.span_interval = span_interval
        config.report_interval = report_interval

        return SamplerScheduler(self, sampler, config)
