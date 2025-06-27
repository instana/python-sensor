# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import platform
import re
import sys
from typing import Dict, List, Tuple, Union

from instana.log import logger


def get_py_source(filename: str) -> Dict[str, str]:
    """
    Retrieves the source code for Python files requested by the UI via the host agent.
    
    This function reads and returns the content of Python source files. It validates
    that the requested file has a .py extension and returns an appropriate error
    message if the file cannot be read or is not a Python file.
    
    Args:
        filename (str): The fully qualified path to a Python source file
        
    Returns:
        Dict[str, str]: A dictionary containing either:
            - {"data": source_code} if successful
            - {"error": error_message} if an error occurred
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


def determine_service_name() -> str:
    """
    Determines the most appropriate service name for this application process.
    
    The service name is determined using the following priority order:
    1. INSTANA_SERVICE_NAME environment variable if set
    2. For specific frameworks:
       - For gunicorn: process title or "gunicorn"
       - For Flask: FLASK_APP environment variable
       - For Django: first part of DJANGO_SETTINGS_MODULE
       - For uwsgi: "uWSGI master/worker [app_name]"
    3. Command line arguments (first non-option argument)
    4. Executable name
    5. "python" as a fallback
    
    Returns:
        str: The determined service name
    """
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

def get_proc_cmdline(as_string: bool = False) -> Union[List[str], str]:
    """
    Parses the process command line from the proc file system.
    
    This function attempts to read the command line of the current process from
    /proc/self/cmdline. If the proc filesystem is not available (e.g., on non-Unix
    systems), it returns a default value.
    
    Args:
        as_string (bool, optional): If True, returns the command line as a single 
                                   space-separated string. If False, returns a list
                                   of command line arguments. Defaults to False.
    
    Returns:
        Union[List[str], str]: The command line as either a list of arguments or a 
                              space-separated string, depending on the as_string parameter.
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


def get_runtime_env_info() -> Tuple[str, str]:
    """
    Returns information about the current runtime environment.
    
    This function collects and returns details about the machine architecture 
    and Python version being used by the application.
    
    Returns:
        Tuple[str, str]: A tuple containing:
            - Machine type (e.g., 'arm64', 'ppc64le')
            - Python version string
    """
    machine = platform.machine()
    python_version = platform.python_version()
    
    return machine, python_version


def log_runtime_env_info() -> None:
    """
    Logs debug information about the current runtime environment.
    
    This function retrieves machine architecture and Python version information
    using get_runtime_env_info() and logs it as a debug message.
    """
    machine, python_version = get_runtime_env_info()
    logger.debug(f"Runtime environment: Machine: {machine}, Python version: {python_version}")

# Made with Bob
