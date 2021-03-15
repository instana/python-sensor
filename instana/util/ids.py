# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys
import time
import random

_rnd = random.Random()
_current_pid = 0

BAD_ID = "BADCAFFE"  # Bad Caffe

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY2:
    string_types = basestring
else:
    string_types = str

def generate_id():
    """ Generate a 64bit base 16 ID for use as a Span or Trace ID """
    global _current_pid

    pid = os.getpid()
    if _current_pid != pid:
        _current_pid = pid
        _rnd.seed(int(1000000 * time.time()) ^ pid)
    new_id = format(_rnd.randint(0, 18446744073709551615), '02x')

    if len(new_id) < 16:
        new_id = new_id.zfill(16)

    return new_id


def header_to_id(header):
    """
    We can receive headers in the following formats:
      1. unsigned base 16 hex string (or bytes) of variable length
      2. [eventual]

    :param header: the header to analyze, validate and convert (if needed)
    :return: a valid ID to be used internal to the tracer
    """
    if PY3 is True and isinstance(header, bytes):
        header = header.decode('utf-8')

    if not isinstance(header, string_types):
        return BAD_ID

    try:
        # Test that header is truly a hexadecimal value before we try to convert
        int(header, 16)

        length = len(header)
        if length < 16:
            # Left pad ID with zeros
            header = header.zfill(16)
        elif length > 16:
            # Phase 0: Discard everything but the last 16byte
            header = header[-16:]

        return header
    except ValueError:
        return BAD_ID
