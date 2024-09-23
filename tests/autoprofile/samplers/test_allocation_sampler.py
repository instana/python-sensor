# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import random
import threading
import time
from typing import Generator, Optional

import pytest

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import min_version, RuntimeInfo
from instana.autoprofile.samplers.allocation_sampler import AllocationSampler


class TestAllocationSampler:
    @pytest.fixture(autouse=True)
    def _resources(self) -> Generator[None, None, None]:
        """SetUp and TearDown"""
        # setup
        # Create a new Profiler.
        self.profiler = Profiler(None)
        self.profiler.start(disable_timers=True)
        yield
        # teardown
        self.profiler.destroy()

    def test_allocation_profile(self) -> None:
        if RuntimeInfo.OS_WIN or not min_version(3, 4):
            return

        sampler = AllocationSampler(self.profiler)
        sampler.setup()
        sampler.reset()

        mem1 = []

        def mem_leak(n: Optional[int] = 100000) -> None:
            mem2 = []
            for i in range(0, n):
                mem1.append(random.randint(0, 1000))
                mem2.append(random.randint(0, 1000))

        def mem_leak2() -> None:
            mem_leak()

        def mem_leak3() -> None:
            mem_leak2()

        def mem_leak4() -> None:
            mem_leak3()

        def mem_leak5() -> None:
            mem_leak4()

        def record() -> None:
            sampler.start_sampler()
            time.sleep(2)
            sampler.stop_sampler()

        t = threading.Thread(target=record)
        t.start()

        # simulate leak
        mem_leak5()

        t.join()

        profile = sampler.build_profile(2000, 120000).to_dict()

        assert "test_allocation_sampler.py" in str(profile)

