# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import unittest
import sys
import threading
import os

from instana import autoprofile
from instana.autoprofile.profiler import Profiler


class FrameCacheTestCase(unittest.TestCase):

    def test_skip_stack(self):
        profiler = Profiler(None)
        profiler.start(disable_timers=True)
        test_profiler_file = os.path.realpath(autoprofile.__file__)
        self.assertTrue(profiler.frame_cache.is_profiler_frame(test_profiler_file))


if __name__ == '__main__':
    unittest.main()
