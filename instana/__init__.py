# coding=utf-8
"""
▀████▀███▄   ▀███▀▄█▀▀▀█▄███▀▀██▀▀███     ██     ▀███▄   ▀███▀     ██
  ██   ███▄    █ ▄██    ▀█▀   ██   ▀█    ▄██▄      ███▄    █      ▄██▄
  ██   █ ███   █ ▀███▄        ██        ▄█▀██▄     █ ███   █     ▄█▀██▄
  ██   █  ▀██▄ █   ▀█████▄    ██       ▄█  ▀██     █  ▀██▄ █    ▄█  ▀██
  ██   █   ▀██▄█ ▄     ▀██    ██       ████████    █   ▀██▄█    ████████
  ██   █     ███ ██     ██    ██      █▀      ██   █     ███   █▀      ██
▄████▄███▄    ██ █▀█████▀   ▄████▄  ▄███▄   ▄████▄███▄    ██ ▄███▄   ▄████▄

https://www.instana.com/

Documentation: https://www.instana.com/docs/
Source Code: https://github.com/instana/python-sensor
"""

from __future__ import absolute_import

import os
import sys
import importlib
from threading import Timer
import pkg_resources

from .version import VERSION

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2020 Instana Inc.'
__credits__ = ['Pavlo Baron', 'Peter Giacomo Lombardo', 'Andrey Slotin']
__license__ = 'MIT'
__maintainer__ = 'Peter Giacomo Lombardo'
__email__ = 'peter.lombardo@instana.com'
__version__ = VERSION

# User configurable EUM API key for instana.helpers.eum_snippet()
# pylint: disable=invalid-name
eum_api_key = ''

# This Python package can be loaded into Python processes one of three ways:
#   1. manual import statement
#   2. autowrapt hook
#   3. dynamically injected remotely
#
# With such magic, we may get pulled into Python processes that we have no interest being in.
# As a safety measure, we maintain a "do not load list" and if this process matches something
# in that list, then we go sit in a corner quietly and don't load anything at all.
do_not_load_list = ["pip", "pip2", "pip3", "pipenv", "docker-compose", "easy_install", "easy_install-2.7",
                    "smtpd.py", "twine", "ufw", "unattended-upgrade"]


def load(_):
    """
    Method used to activate the Instana sensor via AUTOWRAPT_BOOTSTRAP
    environment variable.
    """
    return None

def get_lambda_handler_or_default():
    """
    For instrumenting AWS Lambda, users specify their original lambda handler in the LAMBDA_HANDLER environment
    variable.  This function searches for and parses that environment variable or returns the defaults.

    The default handler value for AWS Lambda is 'lambda_function.lambda_handler' which
    equates to the function "lambda_handler in a file named "lambda_function.py" or in Python
    terms "from lambda_function import lambda_handler"
    """
    handler_module = "lambda_function"
    handler_function = "lambda_handler"

    try:
        handler = os.environ.get("LAMBDA_HANDLER", False)

        if handler:
            parts = handler.split(".")
            handler_function = parts.pop().strip()
            handler_module = ".".join(parts).strip()
    except Exception:
        pass

    return handler_module, handler_function


def lambda_handler(event, context):
    """
    Entry point for AWS Lambda monitoring.

    This function will trigger the initialization of Instana monitoring and then call
    the original user specified lambda handler function.
    """
    module_name, function_name = get_lambda_handler_or_default()

    try:
        # Import the module specified in module_name
        handler_module = importlib.import_module(module_name)
    except ImportError:
        print("Couldn't determine and locate default module handler: %s.%s" % (module_name, function_name))
    else:
        # Now get the function and execute it
        if hasattr(handler_module, function_name):
            handler_function = getattr(handler_module, function_name)
            return handler_function(event, context)
        else:
            print("Couldn't determine and locate default function handler: %s.%s" % (module_name, function_name))


def boot_agent_later():
    """ Executes <boot_agent> in the future! """
    if 'gevent' in sys.modules:
        import gevent # pylint: disable=import-outside-toplevel
        gevent.spawn_later(2.0, boot_agent)
    else:
        Timer(2.0, boot_agent).start()


def boot_agent():
    """Initialize the Instana agent and conditionally load auto-instrumentation."""
    # Disable all the unused-import violations in this function
    # pylint: disable=unused-import
    # pylint: disable=import-outside-toplevel

    import instana.singletons

    # Instrumentation
    if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
        # Import & initialize instrumentation
        from .instrumentation.aws import lambda_inst

        if sys.version_info >= (3, 6, 0):
            from .instrumentation import fastapi_inst
            from .instrumentation import starlette_inst

        if sys.version_info >= (3, 5, 3):
            from .instrumentation import asyncio
            from .instrumentation.aiohttp import client
            from .instrumentation.aiohttp import server
            from .instrumentation import asynqp
            from .instrumentation import boto3_inst

        if sys.version_info[0] < 3:
            from .instrumentation import mysqlpython
            from .instrumentation import webapp2_inst
        else:
            from .instrumentation import mysqlclient

        if sys.version_info[0] >= 3:
            from .instrumentation.google.cloud import storage

        from .instrumentation.celery import hooks

        from .instrumentation import cassandra_inst
        from .instrumentation import couchbase_inst
        from .instrumentation import flask
        from .instrumentation import gevent_inst
        from .instrumentation import grpcio
        from .instrumentation.tornado import client
        from .instrumentation.tornado import server
        from .instrumentation import logging
        from .instrumentation import pymysql
        from .instrumentation import psycopg2
        from .instrumentation import redis
        from .instrumentation import sqlalchemy
        from .instrumentation import sudsjurko
        from .instrumentation import urllib3
        from .instrumentation.django import middleware
        from .instrumentation import pymongo

    # Hooks
    from .hooks import hook_uwsgi

if 'INSTANA_DISABLE' not in os.environ:
    # There are cases when sys.argv may not be defined at load time.  Seems to happen in embedded Python,
    # and some Pipenv installs.  If this is the case, it's best effort.
    if hasattr(sys, 'argv') and len(sys.argv) > 0 and (os.path.basename(sys.argv[0]) in do_not_load_list):
        if "INSTANA_DEBUG" in os.environ:
            print("Instana: No use in monitoring this process type (%s).  "
                  "Will go sit in a corner quietly." % os.path.basename(sys.argv[0]))
    else:
        # AutoProfile
        if "INSTANA_AUTOPROFILE" in os.environ:
            from .singletons import get_profiler
            profiler = get_profiler()
            if profiler:
                profiler.start()

        if "INSTANA_MAGIC" in os.environ:
            pkg_resources.working_set.add_entry("/tmp/.instana/python")
            # The following path is deprecated: To be removed at a future date
            pkg_resources.working_set.add_entry("/tmp/instana/python")

            # If we're being loaded into an already running process, then delay agent initialization
            boot_agent_later()
        else:
            boot_agent()
