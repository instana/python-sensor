# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import signal
import sys
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from types import FrameType

class RuntimeInfo(object):
    OS_LINUX = sys.platform.startswith("linux")
    OS_DARWIN = sys.platform == "darwin"
    OS_WIN = sys.platform == "win32"
    GEVENT = False


try:
    import gevent

    if hasattr(gevent, "_threading"):
        RuntimeInfo.GEVENT = True
except ImportError:
    pass


def min_version(major: int, minor: Optional[int] = 0) -> bool:
    return sys.version_info.major == major and sys.version_info.minor >= minor


def register_signal(
    signal_number: signal.Signals,
    handler_func: Callable[..., object],
    once: Optional[bool] = False,
) -> None:
    prev_handler = None

    def _handler(signum: signal.Signals, frame: "FrameType") -> None:
        skip_prev = handler_func(signum, frame)

        if not skip_prev:
            if callable(prev_handler):
                if once:
                    signal.signal(signum, prev_handler)
                prev_handler(signum, frame)
            elif prev_handler == signal.SIG_DFL and once:
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)

    prev_handler = signal.signal(signal_number, _handler)
