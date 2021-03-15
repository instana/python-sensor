# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import unittest
import threading

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import runtime_info, min_version


# python3 -m unittest discover -v -s tests -p *_test.py

class ProfilerTestCase(unittest.TestCase):

    def test_run_in_main_thread(self):
        if runtime_info.OS_WIN:
            return

        profiler = Profiler(None)
        profiler.start(disable_timers=True)

        result = {}

        def _run():
            result['thread_id'] = threading.current_thread().ident

        def _thread():
            profiler.run_in_main_thread(_run)

        t = threading.Thread(target=_thread)
        t.start()
        t.join()

        self.assertEqual(result['thread_id'], threading.current_thread().ident)
        

if __name__ == '__main__':
    unittest.main()
