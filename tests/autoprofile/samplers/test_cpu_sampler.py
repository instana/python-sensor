# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import threading
from typing import Generator

import pytest

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import RuntimeInfo
from instana.autoprofile.samplers.cpu_sampler import CPUSampler


class TestCPUSampler:
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


    def test_cpu_profile(self) -> None:
        if RuntimeInfo.OS_WIN:
            return

        sampler = CPUSampler(self.profiler)
        sampler.setup()
        sampler.reset()

        def record() -> None:
            sampler.start_sampler()
            time.sleep(2)
            sampler.stop_sampler()

        record_t = threading.Thread(target=record)
        record_t.start()

        def cpu_work_main_thread() -> None:
            for i in range(0, 1000000):
                text = "text1" + str(i)
                text = text + "text2"

        cpu_work_main_thread()

        record_t.join()

        profile = sampler.build_profile(2000, 120000).to_dict()

        assert 'cpu_work_main_thread' in str(profile)
