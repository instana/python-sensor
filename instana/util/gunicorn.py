# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys
from ..log import logger

def running_in_gunicorn():
    """
    Determines if we are running inside of a gunicorn process.

    @return:  Boolean
    """
    process_check = False

    try:
        # Is this a gunicorn process?
        if hasattr(sys, 'argv'):
            for arg in sys.argv:
                if arg.find('gunicorn') >= 0:
                    process_check = True
        elif os.path.isfile("/proc/self/cmdline"):
            with open("/proc/self/cmdline") as cmd:
                contents = cmd.read()

            parts = contents.split('\0')
            parts.pop()
            cmdline = " ".join(parts)

            if cmdline.find('gunicorn') >= 0:
                process_check = True

        return process_check
    except Exception:
        logger.debug("Instana.log.running_in_gunicorn: ", exc_info=True)
        return False