import json
import os
import random
import re
import sys
import time

from collections import defaultdict
import pkg_resources

try:
    from urllib import parse
except ImportError:
    import urlparse as parse
    import urllib

from .log import logger

if sys.version_info.major == 2:
    string_types = basestring
else:
    string_types = str

_rnd = random.Random()
_current_pid = 0

BAD_ID = "BADCAFFE"  # Bad Caffe

# Simple implementation of a nested dictionary.
DictionaryOfStan = lambda: defaultdict(DictionaryOfStan)


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


def get_proc_cmdline(as_string=False):
    """
    Parse the proc file system for the command line of this process.  If not available, then return a default.
    Return is dependent on the value of `as_string`.  If True, return the full command line as a string,
    otherwise a list.
    """
    name = "python"
    if os.path.isfile("/proc/self/cmdline"):
        with open("/proc/self/cmdline") as cmd:
            name = cmd.read()
    else:
        # Most likely not on a *nix based OS.  Return a default
        if as_string is True:
            return name
        else:
            return [name]

    # /proc/self/command line will have strings with null bytes such as "/usr/bin/python\0-s\0-d\0".  This
    # bit will prep the return value and drop the trailing null byte
    parts = name.split('\0')
    parts.pop()

    if as_string is True:
        parts = " ".join(parts)

    return parts


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


def contains_secret(candidate, matcher, kwlist):
    """
    This function will indicate whether <candidate> contains a secret as described here:
    https://www.instana.com/docs/setup_and_manage/host_agent/configuration/#secrets

    :param candidate: string to check
    :param matcher: the matcher to use
    :param kwlist: the list of keywords to match
    :return: boolean
    """
    try:
        if candidate is None or candidate == "INSTANA_AGENT_KEY":
            return False

        if not isinstance(kwlist, list):
            logger.debug("contains_secret: bad keyword list")
            return False

        if matcher == 'equals-ignore-case':
            for keyword in kwlist:
                if candidate.lower() == keyword.lower():
                    return True
        elif matcher == 'equals':
            for keyword in kwlist:
                if candidate == keyword:
                    return True
        elif matcher == 'contains-ignore-case':
            for keyword in kwlist:
                if keyword.lower() in candidate:
                    return True
        elif matcher == 'contains':
            for keyword in kwlist:
                if keyword in candidate:
                    return True
        elif matcher == 'regex':
            for regexp in kwlist:
                if re.match(regexp, candidate):
                    return True
        else:
            logger.debug("contains_secret: unknown matcher")
            return False

    except Exception:
        logger.debug("contains_secret", exc_info=True)


def strip_secrets_from_query(qp, matcher, kwlist):
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

        if not isinstance(kwlist, list):
            logger.debug("strip_secrets_from_query: bad keyword list")
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
            logger.debug("strip_secrets_from_query: unknown matcher")
            return qp

        if sys.version_info < (3, 0):
            result = urllib.urlencode(params, doseq=True)
        else:
            result = parse.urlencode(params, doseq=True)
        query = parse.unquote(result)

        if path:
            query = path + '?' + query

        return query
    except Exception:
        logger.debug("strip_secrets_from_query", exc_info=True)


def sql_sanitizer(sql):
    """
    Removes values from valid SQL statements and returns a stripped version.

    :param sql: The SQL statement to be sanitized
    :return: String - A sanitized SQL statement without values.
    """
    return regexp_sql_values.sub('?', sql)


# Used by sql_sanitizer
regexp_sql_values = re.compile(r"('[\s\S][^']*'|\d*\.\d+|\d+|NULL)")


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


def get_py_source(filename):
    """
    Retrieves and returns the source code for any Python
    files requested by the UI via the host agent

    @param filename [String] The fully qualified path to a file
    """
    response = None
    try:
        if regexp_py.search(filename) is None:
            response = {"error": "Only Python source files are allowed. (*.py)"}
        else:
            pysource = ""
            with open(filename, 'r') as pyfile:
                pysource = pyfile.read()

            response = {"data": pysource}

    except Exception as exc:
        response = {"error": str(exc)}

    return response


# Used by get_py_source
regexp_py = re.compile(r"\.py$")


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


def determine_service_name():
    """ This function makes a best effort to name this application process. """

    # One environment variable to rule them all
    if "INSTANA_SERVICE_NAME" in os.environ:
        return os.environ["INSTANA_SERVICE_NAME"]

    try:
        # Now best effort in naming this process.  No nice package.json like in Node.js
        # so we do best effort detection here.
        app_name = "python"  # the default name

        if not hasattr(sys, 'argv'):
            proc_cmdline = get_proc_cmdline(as_string=False)
            return os.path.basename(proc_cmdline[0])

        basename = os.path.basename(sys.argv[0])
        if basename == "gunicorn":
            if 'setproctitle' in sys.modules:
                # With the setproctitle package, gunicorn renames their processes
                # to pretty things - we use those by default
                # gunicorn: master [djface.wsgi]
                # gunicorn: worker [djface.wsgi]
                app_name = get_proc_cmdline(as_string=True)
            else:
                app_name = basename
        elif "FLASK_APP" in os.environ:
            app_name = os.environ["FLASK_APP"]
        elif "DJANGO_SETTINGS_MODULE" in os.environ:
            app_name = os.environ["DJANGO_SETTINGS_MODULE"].split('.')[0]
        elif basename == '':
            if sys.stdout.isatty():
                app_name = "Interactive Console"
            else:
                # No arguments.  Take executable as app_name
                app_name = os.path.basename(sys.executable)
        else:
            # Last chance.  app_name for "python main.py" would be "main.py" here.
            app_name = basename

        # We should have a good app_name by this point.
        # Last conditional, if uwsgi, then wrap the name
        # with the uwsgi process type
        if basename == "uwsgi":
            # We have an app name by this point.  Now if running under
            # uwsgi, augment the app name
            try:
                import uwsgi

                if app_name == "uwsgi":
                    app_name = ""
                else:
                    app_name = " [%s]" % app_name

                if os.getpid() == uwsgi.masterpid():
                    uwsgi_type = "uWSGI master%s"
                else:
                    uwsgi_type = "uWSGI worker%s"

                app_name = uwsgi_type % app_name
            except ImportError:
                pass
        return app_name
    except Exception:
        logger.debug("get_application_name: ", exc_info=True)
        return app_name


def normalize_aws_lambda_arn(context):
    """
    Parse the AWS Lambda context object for a fully qualified AWS Lambda function ARN.

    This method will ensure that the returned value matches the following ARN pattern:
      arn:aws:lambda:${region}:${account-id}:function:${name}:${version}

    @param context:  AWS Lambda context object
    @return:
    """
    try:
        arn = context.invoked_function_arn
        parts = arn.split(':')

        count = len(parts)
        if count == 7:
            # need to append version
            arn = arn + ':' + context.function_version
        elif count != 8:
            logger.debug("Unexpected ARN parse issue: %s", arn)

        return arn
    except:
        logger.debug("normalize_arn: ", exc_info=True)


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
    except:
        return False
