# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import threading
import time

from ..log import logger


class TimerWraper(object):
    def __init__(self):
        self.timer = None
        self.cancel_lock = threading.Lock()
        self.canceled = False

    def cancel(self):
        with self.cancel_lock:
            self.canceled = True
            self.timer.cancel()


def delay(timeout, func, *args):
    def func_wrapper():
        try:
            func(*args)
        except Exception:
            logger.error('Error in delayed function', exc_info=True)

    t = threading.Timer(timeout, func_wrapper, ())
    t.start()

    return t


def schedule( timeout, interval, func, *args):
    tw = TimerWraper()

    def func_wrapper():
        start = time.time()

        try:
            func(*args)
        except Exception:
            logger.error('Error in scheduled function', exc_info=True)

        with tw.cancel_lock:
            if not tw.canceled:
                tw.timer = threading.Timer(abs(interval - (time.time() - start)), func_wrapper, ())
                tw.timer.start()

    tw.timer = threading.Timer(timeout, func_wrapper, ())
    tw.timer.start()

    return tw