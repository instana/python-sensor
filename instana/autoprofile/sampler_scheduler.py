import time
import random

from ..log import logger
from .profile import Profile
from .profile import CallSite
from .schedule import schedule, delay


class SamplerConfig(object):
    def __init__(self):
        self.log_prefix = None
        self.max_profile_duration = None
        self.max_span_duration = None
        self.span_interval = None
        self.report_interval = None


class SamplerScheduler:
    def __init__(self, profiler, sampler, config):
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

    def setup(self):
        self.sampler.setup()

    def start(self):
        if not self.sampler.ready:
            return

        if self.started:
            return
        self.started = True

        self.reset()

        def random_delay():
            timeout = random.randint(0, round(self.config.span_interval - self.config.max_span_duration))
            self.random_timer = delay(timeout, self.start_profiling)

        if not self.profiler.get_option('disable_timers'):
            self.span_timer = schedule(0, self.config.span_interval, random_delay)
            self.report_timer = schedule(self.config.report_interval, self.config.report_interval, self.report)

    def stop(self):
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

    def destroy(self):
        self.sampler.destroy()

    def reset(self):
        self.sampler.reset()
        self.profile_start_ts = time.time()
        self.profile_duration = 0
        self.span_count = 0

    def start_profiling(self):
        if not self.started:
            return False

        if self.profile_duration > self.config.max_profile_duration:
            logger.debug(self.config.log_prefix + ': max profiling duration reached.')
            return False

        if self.span_count > self.config.max_span_count:
            logger.debug(self.config.log_prefix + ': max recording count reached.')
            return False

        if self.profiler.sampler_active:
            logger.debug(self.config.log_prefix + ': sampler lock exists.')
            return False
        self.profiler.sampler_active = True
        logger.debug(self.config.log_prefix + ': started.')

        try:
            self.sampler.start_sampler()
        except Exception:
            self.profiler.sampler_active = False
            logger.error('Error starting profiling', exc_info=True)
            return False

        self.span_timeout = delay(self.config.max_span_duration, self.stop_profiling)
        
        self.span_active = True
        self.span_start_ts = time.time()
        self.span_count += 1

        return True

    def stop_profiling(self):
        if not self.span_active:
            return
        self.span_active = False

        try:
            self.profile_duration = self.profile_duration + time.time() - self.span_start_ts
            self.sampler.stop_sampler()
        except Exception:
            logger.error('Error stopping profiling', exc_info=True)

        self.profiler.sampler_active = False

        if self.span_timeout:
            self.span_timeout.cancel()

        logger.debug(self.config.log_prefix + ': stopped.')

    def report(self):
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
            to_millis(time.time() - self.profile_start_ts))

        if self.profiler.agent.can_send():
            if self.profiler.agent.announce_data.pid:
                profile.process_id = str(self.profiler.agent.announce_data.pid)

            self.profiler.agent.collector.profile_queue.put(profile.to_dict())

            logger.debug(self.config.log_prefix + ': reporting profile:')
        else:
            logger.debug(self.config.log_prefix + ': not reporting profile, agent not ready')

        self.reset()


def to_millis(t):
    return int(round(t * 1000))
