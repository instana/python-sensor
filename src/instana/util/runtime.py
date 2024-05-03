# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import re
import os
import sys

from ..log import logger

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


def determine_service_name():
    """ This function makes a best effort to name this application process. """

    # One environment variable to rule them all
    if "INSTANA_SERVICE_NAME" in os.environ:
        return os.environ["INSTANA_SERVICE_NAME"]

    # Now best effort in naming this process.  No nice package.json like in Node.js
    # so we do best effort detection here.
    app_name = "python"  # the default name
    basename = None

    try:
        if not hasattr(sys, 'argv'):
            proc_cmdline = get_proc_cmdline(as_string=False)
            return os.path.basename(proc_cmdline[0])

        # Get first argument that is not an CLI option
        for candidate in sys.argv:
            if len(candidate) > 0 and candidate[0] != '-':
                basename = candidate
                break

        # If nothing found, fall back to executable
        if basename is None:
            basename = os.path.basename(sys.executable)
        else:
            # Assure leading paths are stripped
            basename = os.path.basename(basename)

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
    except Exception:
        logger.debug("non-fatal get_application_name: ", exc_info=True)

    return app_name

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