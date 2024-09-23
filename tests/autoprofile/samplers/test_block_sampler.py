# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import threading
import time
from typing import Generator

import pytest

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import RuntimeInfo
from instana.autoprofile.samplers.block_sampler import BlockSampler


class TestBlockSampler:
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

    def test_block_profile(self) -> None:
        if RuntimeInfo.OS_WIN:
            return

        sampler = BlockSampler(self.profiler)
        sampler.setup()
        sampler.reset()

        lock = threading.Lock()
        event = threading.Event()

        def lock_lock() -> None:
            lock.acquire()
            time.sleep(0.5)
            lock.release()

        def lock_wait() -> None:
            lock.acquire()
            lock.release()

        def event_lock() -> None:
            time.sleep(0.5)
            event.set()

        def event_wait() -> None:
            event.wait()

        def record() -> None:
            sampler.start_sampler()
            time.sleep(2)
            sampler.stop_sampler()

        record_t = threading.Thread(target=record)
        record_t.start()

        # simulate lock
        t = threading.Thread(target=lock_lock)
        t.start()

        t = threading.Thread(target=lock_wait)
        t.start()

        # simulate event
        t = threading.Thread(target=event_lock)
        t.start()

        t = threading.Thread(target=event_wait)
        t.start()

        record_t.join()

        profile = sampler.build_profile(2000, 120000).to_dict()
        # print(profile)

        assert "lock_wait" in str(profile)
        assert "event_wait" in str(profile)
