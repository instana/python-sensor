# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import threading
from typing import Generator

import pytest

from instana.autoprofile.profiler import Profiler
from instana.autoprofile.runtime import RuntimeInfo


class TestProfiler:
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

    def test_run_in_main_thread(self) -> None:
        if RuntimeInfo.OS_WIN:
            return

        result = {}

        def _run():
            result["thread_id"] = threading.current_thread().ident

        def _thread():
            self.profiler.run_in_main_thread(_run)

        t = threading.Thread(target=_thread)
        t.start()
        t.join()

        assert threading.current_thread().ident == result["thread_id"]
