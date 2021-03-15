# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import sys
import signal


class runtime_info(object):
    OS_LINUX = (sys.platform.startswith('linux'))
    OS_DARWIN = (sys.platform == 'darwin')
    OS_WIN = (sys.platform == 'win32')
    PYTHON_2 = (sys.version_info.major == 2)
    PYTHON_3 = (sys.version_info.major == 3)
    GEVENT = False

try:
    import gevent
    if hasattr(gevent, '_threading'):
        runtime_info.GEVENT = True
except ImportError:
    pass


def min_version(major, minor=0):
    return (sys.version_info.major == major and sys.version_info.minor >= minor)


def register_signal(signal_number, handler_func, once=False):
    prev_handler = None

    def _handler(signum, frame):
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
