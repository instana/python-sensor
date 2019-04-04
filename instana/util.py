import json
import os
import random
import re
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

BAD_ID = "BADCAFFE"  # Bad Caffe


def generate_id():
    """ Generate a 64bit base 16 ID for use as a Span or Trace ID """
    global _current_pid

    pid = os.getpid()
    if _current_pid != pid:
        _current_pid = pid
        _rnd.seed(int(1000000 * time.time()) ^ pid)
    id = format(_rnd.randint(0, 18446744073709551615), '02x')

    if len(id) < 16:
        id = id.zfill(16)

    return id


def header_to_id(header):
    """
    We can receive headers in the following formats:
      1. unsigned base 16 hex string of variable length
      2. [eventual]

    :param header: the header to analyze, validate and convert (if needed)
    :return: a valid ID to be used internal to the tracer
    """
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


def to_json(obj):
    """
    Convert obj to json.  Used mostly to convert the classes in json_span.py until we switch to nested
    dicts (or something better)

    :param obj: the object to serialize to json
    :return:  json string
    """
    try:
        return json.dumps(obj, default=lambda obj: {k.lower(): v for k, v in obj.__dict__.items()},
                          sort_keys=False, separators=(',', ':')).encode()
    except Exception as e:
        logger.info("to_json: ", e, obj)


def package_version():
    """
    Determine the version of this package.

    :return: String representing known version
    """
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


def get_default_gateway():
    """
    Attempts to read /proc/self/net/route to determine the default gateway in use.

    :return: String - the ip address of the default gateway or None if not found/possible/non-existant
    """
    try:
        # The first line is the header line
        # We look for the line where the Destination is 00000000 - that is the default route
        # The Gateway IP is encoded backwards in hex.
        with open("/proc/self/net/route") as routes:
            for line in routes:
                parts = line.split('\t')
                if '00000000' == parts[1]:
                    hip = parts[2]

        if hip is not None and len(hip) is 8:
            # Reverse order, convert hex to int
            return "%i.%i.%i.%i" % (int(hip[6:8], 16), int(hip[4:6], 16), int(hip[2:4], 16), int(hip[0:2], 16))

    except:
        logger.warn("get_default_gateway: ", exc_info=True)


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


def every(delay, task, name):
    """
    Executes a task every `delay` seconds
    
    :param delay: the delay in seconds
    :param task: the method to run.  The method should return False if you want the loop to stop.
    :return: None
    """
    next_time = time.time() + delay

    while True:
        time.sleep(max(0, next_time - time.time()))
        try:
            if task() is False:
                break
        except Exception:
            logger.debug("Problem while executing repetitive task: %s" % name, exc_info=True)

        # skip tasks if we are behind schedule:
        next_time += (time.time() - next_time) // delay * delay + delay

# Used by get_py_source
regexp_py = re.compile('\.py$')
