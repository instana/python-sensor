# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import unittest
import random
import threading

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import min_version, runtime_info
from instana.autoprofile.samplers.allocation_sampler import AllocationSampler


class AllocationSamplerTestCase(unittest.TestCase):

    def test_allocation_profile(self):
        if runtime_info.OS_WIN or not min_version(3, 4):
            return

        profiler = Profiler(None)
        profiler.start(disable_timers=True)
        sampler = AllocationSampler(profiler)
        sampler.setup()
        sampler.reset()

        mem1 = []
        def mem_leak(n = 100000):
            mem2 = []
            for i in range(0, n):
                mem1.append(random.randint(0, 1000))
                mem2.append(random.randint(0, 1000))

        def mem_leak2():
            mem_leak()

        def mem_leak3():
            mem_leak2()

        def mem_leak4():
            mem_leak3()

        def mem_leak5():
            mem_leak4()

        def record():
            sampler.start_sampler()
            time.sleep(2)
            sampler.stop_sampler()

        t = threading.Thread(target=record)
        t.start()

        # simulate leak
        mem_leak5()

        t.join()

        profile = sampler.build_profile(2000, 120000).to_dict()
        #print(profile)

        self.assertTrue('test_allocation_sampler.py' in str(profile))


if __name__ == '__main__':
    unittest.main()
