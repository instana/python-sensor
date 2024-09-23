# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import signal
import threading
from typing import TYPE_CHECKING, List, Optional, Tuple

from instana.autoprofile.profile import CallSite, Profile
from instana.autoprofile.runtime import RuntimeInfo
from instana.log import logger

if TYPE_CHECKING:
    from types import FrameType


class CPUSampler(object):
    SAMPLING_RATE = 0.01
    MAX_TRACEBACK_SIZE = 25  # number of frames

    def __init__(self, profiler: Profile) -> None:
        self.profiler = profiler
        self.ready = False
        self.top = None
        self.top_lock = threading.Lock()
        self.prev_signal_handler = None
        self.sampler_active = False

    def setup(self) -> None:
        if self.profiler.get_option("cpu_sampler_disabled"):
            return

        if not RuntimeInfo.OS_LINUX and not RuntimeInfo.OS_DARWIN:
            logger.debug("CPU sampler is only supported on Linux and OS X.")
            return

        def _sample(signum: object, signal_frame: "FrameType") -> None:
            if self.sampler_active:
                return
            self.sampler_active = True

            with self.top_lock:
                try:
                    self.process_sample(signal_frame)
                    signal_frame = None
                except Exception:
                    logger.error("Error in signal handler", exc_info=True)

            self.sampler_active = False

        self.prev_signal_handler = signal.signal(signal.SIGPROF, _sample)

        self.ready = True

    def reset(self) -> None:
        self.top = CallSite("", "", 0)

    def start_sampler(self) -> None:
        logger.debug("Activating CPU sampler.")

        signal.setitimer(signal.ITIMER_PROF, self.SAMPLING_RATE, self.SAMPLING_RATE)

    def stop_sampler(self) -> None:
        signal.setitimer(signal.ITIMER_PROF, 0)

    def destroy(self) -> None:
        if not self.ready:
            return

        signal.signal(signal.SIGPROF, self.prev_signal_handler)

    def build_profile(self, duration: int, timespan: int) -> Profile:
        with self.top_lock:
            profile = Profile(
                Profile.CATEGORY_CPU,
                Profile.TYPE_CPU_USAGE,
                Profile.UNIT_SAMPLE,
                self.top.children.values(),
                duration,
                timespan,
            )

            return profile

    def process_sample(self, signal_frame: "FrameType") -> None:
        if self.top:
            if signal_frame:
                stack = self.recover_stack(signal_frame)
                if stack:
                    self.update_profile(self.top, stack)

                stack = None

    def recover_stack(
        self, signal_frame: "FrameType"
    ) -> Optional[List[Tuple[str, str, int]]]:
        stack = []

        depth = 0
        while signal_frame is not None and depth <= self.MAX_TRACEBACK_SIZE:
            if (
                signal_frame.f_code
                and signal_frame.f_code.co_name
                and signal_frame.f_code.co_filename
            ):
                func_name = signal_frame.f_code.co_name
                filename = signal_frame.f_code.co_filename
                lineno = signal_frame.f_lineno

                if filename and self.profiler.frame_cache.is_profiler_frame(filename):
                    return None

                # frame = Frame(func_name, filename, lineno)
                stack.append((func_name, filename, lineno))

                signal_frame = signal_frame.f_back

            depth += 1

        if len(stack) == 0:
            return None
        else:
            return stack

    def update_profile(self, profile: Profile, stack: List[Tuple[str, str, int]]):
        current_node = profile

        for func_name, filename, lineno in reversed(stack):
            current_node = current_node.find_or_add_child(func_name, filename, lineno)

        current_node.increment(1, 1)
