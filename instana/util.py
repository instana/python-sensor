import binascii
import json
import os
import random
import re
import struct
import sys
import time

import pkg_resources

try:
    from urllib import parse
except ImportError:
     import urlparse as parse
     import urllib

from .log import logger


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
    if _current_pid != pid:
        _current_pid = pid
        _rnd.seed(int(1000000 * time.time()) ^ pid)
    return _rnd.randint(-9223372036854775808, 9223372036854775807)


def id_to_header(id):
    """ Convert a 64bit signed integer to an unsigned base 16 hex string """

    try:
        if not isinstance(id, int):
            return BAD_ID_HEADER

        byte_string = struct.pack('>q', id)
        return str(binascii.hexlify(byte_string).decode('UTF-8').lstrip('0'))
    except Exception as e:
        logger.debug(e)
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
        logger.info("to_json: ", e, obj)


def package_version():
    version = ""
    try:
        version = pkg_resources.get_distribution('instana').version
    except pkg_resources.DistributionNotFound:
        version = 'unknown'
    finally:
        return version


def strip_secrets(qp, matcher, kwlist):
    """
    This function will scrub the secrets from a query param string based on the passed in matcher and kwlist.

    blah=1&secret=password&valid=true will result in blah=1&secret=<redacted>&valid=true

    You can even pass in path query combinations:

    /signup?blah=1&secret=password&valid=true will result in /signup?blah=1&secret=<redacted>&valid=true

    :param qp: a string representing the query params in URL form (unencoded)
    :param matcher: the matcher to use
    :param kwlist: the list of keywords to match
    :return: a scrubbed query param string
    """
    path = None

    try:
        if qp is None:
            return ''

        if type(kwlist) is not list:
            logger.debug("strip_secrets: bad keyword list")
            return qp

        # If there are no key=values, then just return
        if not '=' in qp:
            return qp

        if '?' in qp:
            path, query = qp.split('?')
        else:
            query = qp

        params = parse.parse_qsl(query, keep_blank_values=True)
        redacted = ['<redacted>']

        if matcher == 'equals-ignore-case':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if kv[0].lower() == keyword.lower():
                        params[index] = (kv[0], redacted)
        elif matcher == 'equals':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if kv[0] == keyword:
                        params[index] = (kv[0], redacted)
        elif matcher == 'contains-ignore-case':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if keyword.lower() in kv[0].lower():
                        params[index] = (kv[0], redacted)
        elif matcher == 'contains':
            for keyword in kwlist:
                for index, kv in enumerate(params):
                    if keyword in kv[0]:
                        params[index] = (kv[0], redacted)
        elif matcher == 'regex':
            for regexp in kwlist:
                for index, kv in enumerate(params):
                    if re.match(regexp, kv[0]):
                        params[index] = (kv[0], redacted)
        else:
            logger.debug("strip_secrets: unknown matcher")
            return qp

        if sys.version_info < (3, 0):
            result = urllib.urlencode(params, doseq=True)
        else:
            result = parse.urlencode(params, doseq=True)
        query = parse.unquote(result)

        if path:
            query = path + '?' + query

        return query
    except:
        logger.debug("strip_secrets", exc_info=True)

def get_py_source(file):
    """
    Retrieves and returns the source code for any Python
    files requested by the UI via the host agent

    @param file [String] The fully qualified path to a file
    """
    try:
        response = None
        pysource = ""

        if regexp_py.search(file) is None:
            response = {"error": "Only Python source files are allowed. (*.py)"}
        else:
            with open(file, 'r') as pyfile:
                pysource = pyfile.read()

            response = {"data": pysource}

    except Exception as e:
        response = {"error": str(e)}
    finally:
        return response


# Used by get_py_source
regexp_py = re.compile('\.py$')
