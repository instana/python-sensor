# coding=utf-8
# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016
"""
Instana

https://www.ibm.com/products/instana

Documentation: https://www.ibm.com/docs/en/instana-observability/current
Source Code: https://github.com/instana/python-sensor
"""

import importlib
import os
import sys

from instana.collector.helpers.runtime import (
    is_autowrapt_instrumented,
    is_webhook_instrumented,
)
from instana.version import VERSION

__author__ = "Instana Inc."
__copyright__ = "Copyright 2020 Instana Inc."
__credits__ = ["Pavlo Baron", "Peter Giacomo Lombardo", "Andrey Slotin"]
__license__ = "MIT"
__maintainer__ = "Peter Giacomo Lombardo"
__email__ = "peter.lombardo@instana.com"
__version__ = VERSION

# User configurable EUM API key for instana.helpers.eum_snippet()
# pylint: disable=invalid-name
eum_api_key = ""

# This Python package can be loaded into Python processes one of three ways:
#   1. manual import statement
#   2. autowrapt hook
#   3. dynamically injected remotely
#
# With such magic, we may get pulled into Python processes that we have no interest being in.
# As a safety measure, we maintain a "do not load list" and if this process matches something
# in that list, then we go sit in a corner quietly and don't load anything at all.
do_not_load_list = [
    "pip",
    "pip2",
    "pip3",
    "pipenv",
    "docker-compose",
    "easy_install",
    "easy_install-2.7",
    "smtpd.py",
    "twine",
    "ufw",
    "unattended-upgrade",
]


def load(_):
    """
    Method used to activate the Instana sensor via AUTOWRAPT_BOOTSTRAP
    environment variable.
    """
    # Work around https://bugs.python.org/issue32573
    if not hasattr(sys, "argv"):
        sys.argv = [""]
    return None


def apply_gevent_monkey_patch():
    from gevent import monkey

    if os.environ.get("INSTANA_GEVENT_MONKEY_OPTIONS"):

        def short_key(k):
            return k[3:] if k.startswith("no-") else k

        def key_to_bool(k):
            return not k.startswith("no-")

        import inspect

        all_accepted_patch_all_args = inspect.getfullargspec(monkey.patch_all)[0]
        provided_options = (
            os.environ.get("INSTANA_GEVENT_MONKEY_OPTIONS")
            .replace(" ", "")
            .replace("--", "")
            .split(",")
        )
        provided_options = [
            k for k in provided_options if short_key(k) in all_accepted_patch_all_args
        ]

        fargs = {
            short_key(k): key_to_bool(k)
            for (k, v) in zip(provided_options, [True] * len(provided_options))
        }
        monkey.patch_all(**fargs)
    else:
        monkey.patch_all()


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
        print(
            "Couldn't determine and locate default module handler: %s.%s"
            % (module_name, function_name)
        )
    else:
        # Now get the function and execute it
        if hasattr(handler_module, function_name):
            handler_function = getattr(handler_module, function_name)
            return handler_function(event, context)
        else:
            print(
                "Couldn't determine and locate default function handler: %s.%s"
                % (module_name, function_name)
            )


def boot_agent():
    """Initialize the Instana agent and conditionally load auto-instrumentation."""

    import instana.singletons  # noqa: F401

    # Instrumentation
    if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
        # TODO: remove the following entries as the migration of the
        # instrumentation codes are finalised.

        # Import & initialize instrumentation
        # from instana.instrumentation.aws import lambda_inst  # noqa: F401

        # from instana.instrumentation import sanic_inst  # noqa: F401

        # from instana.instrumentation import starlette_inst  # noqa: F401
        # from instana.instrumentation import asyncio  # noqa: F401
        # from instana.instrumentation.aiohttp import client  # noqa: F401
        # from instana.instrumentation.aiohttp import server  # noqa: F401
        # from instana.instrumentation import boto3_inst  # noqa: F401
        # from instana.instrumentation import mysqlclient  # noqa: F401
        # from instana.instrumentation.google.cloud import storage  # noqa: F401
        # from instana.instrumentation.google.cloud import pubsub  # noqa: F401
        # from instana.instrumentation.celery import hooks  # noqa: F401
        # from instana.instrumentation import cassandra_inst  # noqa: F401
        # from instana.instrumentation import couchbase_inst  # noqa: F401
        # from instana.instrumentation import gevent_inst  # noqa: F401
        # from instana.instrumentation import grpcio  # noqa: F401
        # from instana.instrumentation.tornado import client  # noqa: F401
        # from instana.instrumentation.tornado import server  # noqa: F401
        # from instana.instrumentation import pika  # noqa: F401
        # from instana.instrumentation import pymysql  # noqa: F401
        # from instana.instrumentation import psycopg2  # noqa: F401
        # from instana.instrumentation import redis  # noqa: F401
        # from instana.instrumentation import sqlalchemy  # noqa: F401
        from instana.instrumentation import (
            fastapi_inst,  # noqa: F401
            flask,  # noqa: F401
            logging,  # noqa: F401
            urllib3,  # noqa: F401
        )
        # from instana.instrumentation.django import middleware  # noqa: F401
        # from instana.instrumentation import pymongo  # noqa: F401

    # Hooks
    # from instana.hooks import hook_uwsgi  # noqa: F401


if "INSTANA_DISABLE" not in os.environ:
    # There are cases when sys.argv may not be defined at load time.  Seems to happen in embedded Python,
    # and some Pipenv installs.  If this is the case, it's best effort.
    if (
        hasattr(sys, "argv")
        and len(sys.argv) > 0
        and (os.path.basename(sys.argv[0]) in do_not_load_list)
    ):
        if "INSTANA_DEBUG" in os.environ:
            print(
                "Instana: No use in monitoring this process type (%s).  "
                "Will go sit in a corner quietly." % os.path.basename(sys.argv[0])
            )
    else:
        # Automatic gevent monkey patching
        # unless auto instrumentation is off, then the customer should do manual gevent monkey patching
        if (
            (is_autowrapt_instrumented() or is_webhook_instrumented())
            and "INSTANA_DISABLE_AUTO_INSTR" not in os.environ
            and importlib.util.find_spec("gevent")
        ):
            apply_gevent_monkey_patch()
        # AutoProfile
        if "INSTANA_AUTOPROFILE" in os.environ:
            from .singletons import get_profiler

            profiler = get_profiler()
            if profiler:
                profiler.start()

        boot_agent()
