# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import time
import unittest
import random
import threading

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import runtime_info
from instana.autoprofile.samplers.block_sampler import BlockSampler


class BlockSamplerTestCase(unittest.TestCase):
    def test_block_profile(self):
        if runtime_info.OS_WIN:
            return

        profiler = Profiler(None)
        profiler.start(disable_timers=True)
        sampler = BlockSampler(profiler)
        sampler.setup()
        sampler.reset()

        lock = threading.Lock()
        event = threading.Event()

        def lock_lock():
            lock.acquire()
            time.sleep(0.5)
            lock.release()

        def lock_wait():
            lock.acquire()
            lock.release()


        def event_lock():
            time.sleep(0.5)
            event.set()


        def event_wait():
            event.wait()

        def record():
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
        #print(profile)

        self.assertTrue('lock_wait' in str(profile))
        self.assertTrue('event_wait' in str(profile))


if __name__ == '__main__':
    unittest.main()
