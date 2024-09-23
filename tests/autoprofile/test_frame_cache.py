# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
from typing import Generator

import pytest

from instana import autoprofile
from instana.autoprofile.profiler import Profiler


class TestFrameCache:
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

    def test_skip_stack(self) -> None:
        test_profiler_file = os.path.realpath(autoprofile.__file__)

        assert self.profiler.frame_cache.is_profiler_frame(test_profiler_file)
