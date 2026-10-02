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
from importlib import util as importlib_util
from instana.collector.helpers.runtime import (
    is_autowrapt_instrumented,
    is_webhook_instrumented,
)
from instana.util.config import is_truthy
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
    """Activate the Instana Tracer via the AUTOWRAPT_BOOTSTRAP environment variable."""
    # Work around https://bugs.python.org/issue32573
    if not hasattr(sys, "argv"):
        sys.argv = [""]
    return None


def apply_gevent_monkey_patch() -> None:
    from gevent import monkey

    if provided_options := os.environ.get("INSTANA_GEVENT_MONKEY_OPTIONS"):

        def short_key(k: str) -> str:
            return k[3:] if k.startswith("no-") else k

        def key_to_bool(k: str) -> bool:
            return not k.startswith("no-")

        import inspect

        all_accepted_patch_all_args = inspect.getfullargspec(monkey.patch_all)[0]
        provided_options = (
            provided_options.replace(" ", "").replace("--", "").split(",")
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


# Guards against boot_agent() being called more than once when monkey_patch()
# is invoked multiple times in the same process (e.g. application code also
# calls it after Instana has already wrapped it).
_eventlet_booted = False


def _defer_boot_until_eventlet_patch() -> None:
    """Defer boot_agent() until after eventlet.monkey_patch() has been called.

    Strategy
    --------
    Two ``wrapt.when_imported`` hooks are always registered — one for the
    gunicorn eventlet worker path and one for the bare ``monkey_patch()`` path.
    The decision of *which* hook actually boots is made at runtime by checking
    ``sys.modules``, not by inspecting whether gunicorn is installed:

    Hook 1 — ``gunicorn.workers.geventlet`` (gunicorn -k eventlet):
        Wraps ``EventletWorker.patch()``, which gunicorn calls only post-fork
        inside the worker process (``init_process → self.patch()``).
        ``when_imported`` is a no-op if the module is never loaded, so
        gunicorn ≥26 (which removed this worker) and non-eventlet worker
        classes never trigger it.

    Hook 2 — ``eventlet.monkey_patch`` (bare application use):
        Fires for every other caller (plain scripts, ``socketio.run()``,
        gunicorn ≥26, etc.).  If Hook 1 already booted the agent — i.e.
        ``gunicorn.workers.geventlet`` is in ``sys.modules`` — this hook
        skips the boot so the arbiter is never initialised when
        ``--preload`` causes ``monkey_patch()`` to be called there.

    Why ``sys.modules`` instead of ``find_spec("gunicorn")``:
        ``find_spec`` answers "is gunicorn *installed*?", not "is this
        process running under gunicorn's eventlet worker?".  A gunicorn ≥26
        installation, or any non-eventlet worker, would suppress Hook 2
        with the old ``find_spec`` branch, leaving no boot path at all.
    """
    import wrapt

    def _boot_once() -> None:
        global _eventlet_booted
        if not _eventlet_booted:
            _eventlet_booted = True
            if is_truthy(os.environ.get("INSTANA_AUTOPROFILE", None)):
                _start_profiler()
            boot_agent()

    # Hook 1: gunicorn -k eventlet — boots in the worker, after monkey_patch().
    # Gunicorn resolves worker_class in Arbiter.setup() before preload_app, so
    # geventlet is imported in the arbiter. when_imported fires there and wraps
    # EventletWorker.patch; the wrapper itself runs post-fork in the worker.
    @wrapt.when_imported("gunicorn.workers.geventlet")
    def _on_geventlet_imported(module: object) -> None:
        def _after_worker_patch(
            wrapped: object,
            instance: object,
            args: tuple[object, ...],
            kwargs: dict[str, object],
        ) -> object:
            result = wrapped(*args, **kwargs)
            _boot_once()
            return result

        wrapt.wrap_function_wrapper(
            module,
            "EventletWorker.patch",
            _after_worker_patch,
        )

    # Hook 2: bare monkey_patch() call — covers every non-gunicorn scenario and
    # gunicorn ≥26 / non-eventlet-worker setups.  Skips boot when Hook 1 already
    # handled it (geventlet in sys.modules) to prevent arbiter-side boot under
    # --preload.
    @wrapt.when_imported("eventlet")
    def _on_eventlet_imported(module: object) -> None:
        def _after_monkey_patch(
            wrapped: object,
            instance: object,
            args: tuple[object, ...],
            kwargs: dict[str, object],
        ) -> object:
            result = wrapped(*args, **kwargs)
            if "gunicorn.workers.geventlet" not in sys.modules:
                _boot_once()
            return result

        wrapt.wrap_function_wrapper(module, "monkey_patch", _after_monkey_patch)


def get_aws_lambda_handler() -> tuple[str, str]:
    """Return the AWS Lambda handler module and function name.

    Users specify their original lambda handler in the LAMBDA_HANDLER
    environment variable.  This function searches for and parses that
    environment variable or returns the defaults.

    The default handler value for AWS Lambda is 'lambda_function.lambda_handler'
    which equates to the function ``lambda_handler`` in a file named
    ``lambda_function.py``, or in Python terms
    ``from lambda_function import lambda_handler``.
    """
    handler_module = "lambda_function"
    handler_function = "lambda_handler"

    try:
        if handler := os.environ.get("LAMBDA_HANDLER", None):
            parts = handler.split(".")
            handler_function = parts.pop().strip()
            handler_module = ".".join(parts).strip()
    except Exception as exc:
        print(f"get_aws_lambda_handler error: {exc}")

    return handler_module, handler_function


def lambda_handler(event: str, context: str) -> None:
    """Entry point for AWS Lambda monitoring.

    Triggers the initialization of Instana monitoring and then calls
    the original user-specified lambda handler function.
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
    """Initialize the Instana agent and conditionally load auto-instrumentation.

    Imports all instrumentation modules unless INSTANA_DISABLE_AUTO_INSTR is set.
    """

    import instana.singletons  # noqa: F401

    # Import & initialize instrumentation
    if "INSTANA_DISABLE_AUTO_INSTR" not in os.environ:
        from instana.instrumentation import (
            aio_pika,  # noqa: F401
            aioamqp,  # noqa: F401
            asyncio,  # noqa: F401
            cassandra,  # noqa: F401
            celery,  # noqa: F401
            couchbase,  # noqa: F401
            elasticsearch,  # noqa: F401
            fastapi,  # noqa: F401
            flask,  # noqa: F401
            gevent,  # noqa: F401
            grpcio,  # noqa: F401
            httpx,  # noqa: F401
            logging,  # noqa: F401
            mysqlclient,  # noqa: F401
            pep0249,  # noqa: F401
            pika,  # noqa: F401
            psycopg2,  # noqa: F401
            pymongo,  # noqa: F401
            pymssql,  # noqa: F401
            pymysql,  # noqa: F401
            pyramid,  # noqa: F401
            redis,  # noqa: F401
            sanic,  # noqa: F401
            spyne,  # noqa: F401
            sqlalchemy,  # noqa: F401
            starlette,  # noqa: F401
            urllib3,  # noqa: F401
            werkzeug,  # noqa: F401
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
        from instana.instrumentation.twisted import (
            client as twisted_client,  # noqa: F401
        )
        from instana.instrumentation.twisted import (
            server as twisted_server,  # noqa: F401
        )


def _start_profiler() -> None:
    """Start the Instana Auto Profile.

    Retrieves the profiler singleton and starts it if available.
    """
    from instana.singletons import get_profiler

    if profiler := get_profiler():
        profiler.start()


if "INSTANA_DISABLE" in os.environ:  # pragma: no cover
    import warnings

    message = "Instana: The INSTANA_DISABLE environment variable is deprecated. Please use INSTANA_TRACING_DISABLE=True instead."
    warnings.simplefilter("always")
    warnings.warn(message, DeprecationWarning)


if not is_truthy(os.environ.get("INSTANA_TRACING_DISABLE", None)):
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
        if (
            (is_autowrapt_instrumented() or is_webhook_instrumented())
            and "INSTANA_DISABLE_AUTO_INSTR" not in os.environ
        ):
            # Automatic gevent monkey patching
            # unless auto instrumentation is off, then the customer should do manual gevent monkey patching
            if importlib_util.find_spec("gevent"):
                apply_gevent_monkey_patch()

            # Eventlet deferred boot: opt-in via INSTANA_EVENTLET_DEFERRED_BOOT=true.
            # When set, boot_agent() is deferred until after eventlet.monkey_patch() to
            # prevent the ssl.SSLContext RecursionError with gunicorn eventlet workers.
            # Without the opt-in we boot immediately, avoiding silent tracing gaps when
            # eventlet is installed as a transitive dependency but not actually in use
            # (e.g. sync/gthread workers, Celery, plain scripts).
            if importlib_util.find_spec("eventlet") and is_truthy(
                os.environ.get("INSTANA_EVENTLET_DEFERRED_BOOT", None)
            ):
                # boot_agent() will be called by the wrapper after monkey_patch;
                # do not call it here to avoid a double boot.
                _defer_boot_until_eventlet_patch()
                return_early = True
            else:
                return_early = False
        else:
            return_early = False

        if not return_early:
            # AutoProfile
            if is_truthy(os.environ.get("INSTANA_AUTOPROFILE", None)):
                _start_profiler()

            boot_agent()
