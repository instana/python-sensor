import random
import os
import json
import time
import struct
import binascii
from instana import log

import sys
if sys.version_info.major is 2:
    string_types = basestring
else:
    string_types = str

_rnd = random.Random()
_current_pid = 0

BAD_ID_LONG = 3135097598  # Bad Cafe in base 10
BAD_ID_HEADER = "BADDCAFE"  # Bad Cafe


def generate_id():
    """ Generate a 64bit signed integer for use as a Span or Trace ID """
    global _current_pid

    pid = os.getpid()
    if (_current_pid != pid):
        _current_pid = pid
        _rnd.seed(int(1000000 * time.time()) ^ pid)
    return _rnd.randint(-9223372036854775808, 9223372036854775807)


def id_to_header(id):
    """ Convert a 64bit signed integer to an unsigned base 16 hex string """

    try:
        if not isinstance(id, int):
            return BAD_ID_HEADER

        byteString = struct.pack('>q', id)
        return str(binascii.hexlify(byteString).decode('UTF-8').lstrip('0'))
    except Exception as e:
        log.debug(e)
        return BAD_ID_HEADER


def header_to_id(header):
    """ Convert an unsigned base 16 hex string into a 64bit signed integer """

    if not isinstance(header, string_types):
        return BAD_ID_LONG

    try:
        # Test that header is truly a hexadecimal value before we try to convert
        int(header, 16)

        # Pad the header to 16 chars
        header = header.zfill(16)
        r = binascii.unhexlify(header)
        return struct.unpack('>q', r)[0]
    except ValueError:
        return BAD_ID_LONG


def to_json(obj):
    try:
        return json.dumps(obj, default=lambda obj: {k.lower(): v for k, v in obj.__dict__.items()},
                          sort_keys=False, separators=(',', ':')).encode()
    except Exception as e:
        log.info("to_json: ", e, obj)
