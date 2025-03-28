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
from typing import Tuple

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


def load(_: object) -> None:
    """
    Method used to activate the Instana sensor via AUTOWRAPT_BOOTSTRAP
    environment variable.
    """
    # Work around https://bugs.python.org/issue32573
    if not hasattr(sys, "argv"):
        sys.argv = [""]
    return None


def apply_gevent_monkey_patch() -> None:
    from gevent import monkey

    if os.environ.get("INSTANA_GEVENT_MONKEY_OPTIONS"):

        def short_key(k: str) -> str:
            return k[3:] if k.startswith("no-") else k

        def key_to_bool(k: str) -> bool:
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


def get_aws_lambda_handler() -> Tuple[str, str]:
    """
    For instrumenting AWS Lambda, users specify their original lambda handler
    in the LAMBDA_HANDLER environment variable.  This function searches for and
    parses that environment variable or returns the defaults.

    The default handler value for AWS Lambda is 'lambda_function.lambda_handler'
    which equates to the function "lambda_handler in a file named
    lambda_function.py" or in Python terms
    "from lambda_function import lambda_handler"
    """
    handler_module = "lambda_function"
    handler_function = "lambda_handler"

    try:
        handler = os.environ.get("LAMBDA_HANDLER", False)

        if handler:
            parts = handler.split(".")
            handler_function = parts.pop().strip()
            handler_module = ".".join(parts).strip()
    except Exception as exc:
        print(f"get_aws_lambda_handler error: {exc}")

    return handler_module, handler_function


def lambda_handler(event: str, context: str) -> None:
    """
    Entry point for AWS Lambda monitoring.

    This function will trigger the initialization of Instana monitoring and then call
    the original user specified lambda handler function.
    """
    module_name, function_name = get_aws_lambda_handler()

    try:
        # Import the module specified in module_name
        handler_module = importlib.import_module(module_name)
    except ImportError:
        print(
            f"Couldn't determine and locate default module handler: {module_name}.{function_name}"
        )
    else:
        # Now get the function and execute it
        if hasattr(handler_module, function_name):
            handler_function = getattr(handler_module, function_name)
            return handler_function(event, context)
        else:
            print(
                f"Couldn't determine and locate default function handler: {module_name}.{function_name}"
            )


def boot_agent() -> None:
    """Initialize the Instana agent and conditionally load auto-instrumentation."""

    import instana.singletons  # noqa: F401

    # Instrumentation
    if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
        # TODO: remove the following entries as the migration of the
        # instrumentation codes are finalised.

        # Import & initialize instrumentation
        from instana.instrumentation import (
            aioamqp,  # noqa: F401
            asyncio,  # noqa: F401
            cassandra,  # noqa: F401
            celery,  # noqa: F401
            couchbase,  # noqa: F401
            fastapi,  # noqa: F401
            flask,  # noqa: F401
            # gevent_inst,  # noqa: F401
            grpcio,  # noqa: F401
            httpx,  # noqa: F401
            logging,  # noqa: F401
            mysqlclient,  # noqa: F401
            pep0249,  # noqa: F401
            pika,  # noqa: F401
            psycopg2,  # noqa: F401
            pymongo,  # noqa: F401
            pymysql,  # noqa: F401
            pyramid,  # noqa: F401
            redis,  # noqa: F401
            sanic,  # noqa: F401
            sqlalchemy,  # noqa: F401
            starlette,  # noqa: F401
            urllib3,  # noqa: F401
            spyne,  # noqa: F401
            aio_pika,  # noqa: F401
        )
        from instana.instrumentation.aiohttp import (
            client as aiohttp_client,  # noqa: F401
        )
        from instana.instrumentation.aiohttp import (
            server as aiohttp_server,  # noqa: F401
        )
        from instana.instrumentation.aws import (
            boto3,  # noqa: F401
            lambda_inst,  # noqa: F401
        )
        from instana.instrumentation.django import middleware  # noqa: F401
        from instana.instrumentation.google.cloud import (
            pubsub,  # noqa: F401
            storage,  # noqa: F401
        )
        from instana.instrumentation.kafka import (
            confluent_kafka_python,  # noqa: F401
            kafka_python,  # noqa: F401
        )
        from instana.instrumentation.tornado import (
            client as tornado_client,  # noqa: F401
        )
        from instana.instrumentation.tornado import (
            server as tornado_server,  # noqa: F401
        )

    # Hooks
    from instana.hooks import (
        hook_gunicorn,  # noqa: F401
        hook_uwsgi,  # noqa: F401
    )


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
                f"Instana: No use in monitoring this process type ({os.path.basename(sys.argv[0])}). Will go sit in a corner quietly."
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
            from instana.singletons import get_profiler

            profiler = get_profiler()
            if profiler:
                profiler.start()

        boot_agent()
