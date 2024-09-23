# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import random
import time
from typing import TYPE_CHECKING, Union

from instana.autoprofile.schedule import delay, schedule
from instana.log import logger

if TYPE_CHECKING:
    from instana.autoprofile.profiler import Profiler
    from instana.autoprofile.samplers.allocation_sampler import AllocationSampler
    from instana.autoprofile.samplers.block_sampler import BlockSampler
    from instana.autoprofile.samplers.cpu_sampler import CPUSampler


class SamplerConfig(object):
    def __init__(self) -> None:
        self.log_prefix = None
        self.max_profile_duration = None
        self.max_span_duration = None
        self.span_interval = None
        self.report_interval = None


class SamplerScheduler:
    def __init__(
        self,
        profiler: "Profiler",
        sampler: Union["AllocationSampler", "BlockSampler", "CPUSampler"],
        config: SamplerConfig,
    ) -> None:
        self.profiler = profiler
        self.sampler = sampler
        self.config = config
        self.started = False
        self.span_timer = None
        self.span_timeout = None
        self.random_timer = None
        self.report_timer = None
        self.profile_start_ts = None
        self.profile_duration = None
        self.span_active = False
        self.span_start_ts = None
        self.span_count = 0

    def setup(self) -> None:
        self.sampler.setup()

    def start(self) -> None:
        if not self.sampler.ready:
            return

        if self.started:
            return

        self.started = True
        self.reset()

        def random_delay() -> None:
            timeout = random.randint(
                0, round(self.config.span_interval - self.config.max_span_duration)
            )
            self.random_timer = delay(timeout, self.start_profiling)

        if not self.profiler.get_option("disable_timers"):
            self.span_timer = schedule(0, self.config.span_interval, random_delay)
            self.report_timer = schedule(
                self.config.report_interval, self.config.report_interval, self.report
            )

    def stop(self) -> None:
        if not self.started:
            return

        self.started = False

        if self.span_timer:
            self.span_timer.cancel()
            self.span_timer = None

        if self.random_timer:
            self.random_timer.cancel()
            self.random_timer = None

        if self.report_timer:
            self.report_timer.cancel()
            self.report_timer = None

        self.stop_profiling()

    def destroy(self) -> None:
        self.sampler.destroy()

    def reset(self) -> None:
        self.sampler.reset()
        self.profile_start_ts = time.time()
        self.profile_duration = 0
        self.span_count = 0

    def start_profiling(self) -> bool:
        if not self.started:
            return False

        if self.profile_duration > self.config.max_profile_duration:
            logger.debug(f"{self.config.log_prefix}: max profiling duration reached.")
            return False

        if self.span_count > self.config.max_span_count:
            logger.debug(f"{self.config.log_prefix}: max recording count reached.")
            return False

        if self.profiler.sampler_active:
            logger.debug(f"{self.config.log_prefix}: sampler lock exists.")
            return False

        self.profiler.sampler_active = True
        logger.debug(f"{self.config.log_prefix}: started.")

        try:
            self.sampler.start_sampler()
        except Exception:
            self.profiler.sampler_active = False
            logger.error("Error starting profiling", exc_info=True)
            return False

        self.span_timeout = delay(self.config.max_span_duration, self.stop_profiling)

        self.span_active = True
        self.span_start_ts = time.time()
        self.span_count += 1

        return True

    def stop_profiling(self) -> None:
        if not self.span_active:
            return

        self.span_active = False

        try:
            self.profile_duration = (
                self.profile_duration + time.time() - self.span_start_ts
            )
            self.sampler.stop_sampler()
        except Exception:
            logger.error("Error stopping profiling", exc_info=True)

        self.profiler.sampler_active = False

        if self.span_timeout:
            self.span_timeout.cancel()

        logger.debug(f"{self.config.log_prefix}: stopped.")

    def report(self) -> None:
        if not self.started:
            return

        if self.profile_duration == 0:
            return

        if self.profile_start_ts > time.time() - self.config.report_interval:
            return
        elif self.profile_start_ts < time.time() - 2 * self.config.report_interval:
            self.reset()
            return

        profile = self.sampler.build_profile(
            to_millis(self.profile_duration),
            to_millis(time.time() - self.profile_start_ts),
        )

        if self.profiler.agent.can_send():
            if self.profiler.agent.announce_data.pid:
                profile.process_id = str(self.profiler.agent.announce_data.pid)

            self.profiler.agent.collector.profile_queue.put(profile.to_dict())

            logger.debug(f"{self.config.log_prefix}: reporting profile:")
        else:
            logger.debug(
                f"{self.config.log_prefix}: not reporting profile, agent not ready"
            )

        self.reset()


def to_millis(t: int) -> int:
    return int(round(t * 1000))
