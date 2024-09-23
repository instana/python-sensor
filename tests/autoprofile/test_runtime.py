# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import signal
from typing import TYPE_CHECKING

from instana.autoprofile.runtime import RuntimeInfo, register_signal

if TYPE_CHECKING:
    from types import FrameType


class TestRuntime:
    def test_register_signal(self) -> None:
        if RuntimeInfo.OS_WIN:
            return

        result = {"handler": 0}

        def _handler(signum: signal.Signals, frame: "FrameType") -> None:
            result["handler"] += 1

        register_signal(signal.SIGUSR1, _handler)

        os.kill(os.getpid(), signal.SIGUSR1)
        os.kill(os.getpid(), signal.SIGUSR1)

        signal.signal(signal.SIGUSR1, signal.SIG_DFL)

        assert result["handler"] == 2
