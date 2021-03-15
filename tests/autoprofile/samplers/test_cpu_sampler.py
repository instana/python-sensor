# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import time
import unittest
import random
import threading
import sys
import traceback

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import runtime_info
from instana.autoprofile.samplers.cpu_sampler import CPUSampler


class CPUSamplerTestCase(unittest.TestCase):

    def test_cpu_profile(self):
        if runtime_info.OS_WIN:
            return

        profiler = Profiler(None)
        profiler.start(disable_timers=True)
        sampler = CPUSampler(profiler)
        sampler.setup()
        sampler.reset()

        def record():
            sampler.start_sampler()
            time.sleep(2)
            sampler.stop_sampler()

        record_t = threading.Thread(target=record)
        record_t.start()

        def cpu_work_main_thread():
            for i in range(0, 1000000):
                text = "text1" + str(i)
                text = text + "text2"
        cpu_work_main_thread()

        record_t.join()

        profile = sampler.build_profile(2000, 120000).to_dict()
        #print(profile)

        self.assertTrue('cpu_work_main_thread' in str(profile))


if __name__ == '__main__':
    unittest.main()
