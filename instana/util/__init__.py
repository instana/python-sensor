# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import json
import sys
import time

from collections import defaultdict
import pkg_resources

try:
    from urllib import parse
except ImportError:
    import urlparse as parse
    import urllib

from ..log import logger

if sys.version_info.major == 2:
    string_types = basestring
else:
    string_types = str

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

def nested_dictionary():
    return defaultdict(DictionaryOfStan)

# Simple implementation of a nested dictionary.
DictionaryOfStan = nested_dictionary


def to_json(obj):
    """
    Convert obj to json.  Used mostly to convert the classes in json_span.py until we switch to nested
    dicts (or something better)

    :param obj: the object to serialize to json
    :return:  json string
    """
    try:
        def extractor(o):
            if not hasattr(o, '__dict__'):
                logger.debug("Couldn't serialize non dict type: %s", type(o))
                return {}
            else:
                return {k.lower(): v for k, v in o.__dict__.items() if v is not None}

        return json.dumps(obj, default=extractor, sort_keys=False, separators=(',', ':')).encode()
    except Exception:
        logger.debug("to_json non-fatal encoding issue: ", exc_info=True)

def to_pretty_json(obj):
    """
    Convert obj to pretty json.  Used mostly in logging/debugging.

    :param obj: the object to serialize to json
    :return:  json string
    """
    try:
        def extractor(o):
            if not hasattr(o, '__dict__'):
                logger.debug("Couldn't serialize non dict type: %s", type(o))
                return {}
            else:
                return {k.lower(): v for k, v in o.__dict__.items() if v is not None}

        return json.dumps(obj, default=extractor, sort_keys=True, indent=4, separators=(',', ':'))
    except Exception:
        logger.debug("to_pretty_json non-fatal encoding issue: ", exc_info=True)


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

    return version


def get_default_gateway():
    """
    Attempts to read /proc/self/net/route to determine the default gateway in use.

    :return: String - the ip address of the default gateway or None if not found/possible/non-existant
    """
    try:
        hip = None
        # The first line is the header line
        # We look for the line where the Destination is 00000000 - that is the default route
        # The Gateway IP is encoded backwards in hex.
        with open("/proc/self/net/route") as routes:
            for line in routes:
                parts = line.split('\t')
                if parts[1] == '00000000':
                    hip = parts[2]

        if hip is not None and len(hip) == 8:
            # Reverse order, convert hex to int
            return "%i.%i.%i.%i" % (int(hip[6:8], 16), int(hip[4:6], 16), int(hip[2:4], 16), int(hip[0:2], 16))

    except Exception:
        logger.warning("get_default_gateway: ", exc_info=True)


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
            logger.debug("Problem while executing repetitive task: %s", name, exc_info=True)

        # skip tasks if we are behind schedule:
        next_time += (time.time() - next_time) // delay * delay + delay


def validate_url(url):
    """
    Validate if <url> is a valid url

    Examples:
    - "http://localhost:5000" - valid
    - "http://localhost:5000/path" - valid
    - "sandwich" - invalid

    @param url: string
    @return: Boolean
    """
    try:
        result = parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        pass

    return False
