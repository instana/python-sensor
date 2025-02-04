# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""Collection helper for the Python runtime"""

import gc
import importlib.metadata
import os
import platform
import resource
import sys
import threading
from types import ModuleType
from typing import Any, Dict, List, Union, Callable

from instana.collector.helpers.base import BaseHelper
from instana.log import logger
from instana.util import DictionaryOfStan
from instana.util.runtime import determine_service_name
from instana.version import VERSION
from instana.collector.base import BaseCollector

PATH_OF_DEPRECATED_INSTALLATION_VIA_HOST_AGENT = "/tmp/.instana/python"

PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR = "/opt/instana/instrumentation/python/"


def is_autowrapt_instrumented() -> bool:
    return "instana" in os.environ.get("AUTOWRAPT_BOOTSTRAP", ())


def is_webhook_instrumented() -> bool:
    return any(map(lambda p: PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR in p, sys.path))


class RuntimeHelper(BaseHelper):
    """Helper class to collect snapshot and metrics for this Python runtime"""

    def __init__(
        self,
        collector: BaseCollector,
    ) -> None:
        super(RuntimeHelper, self).__init__(collector)
        self.previous = DictionaryOfStan()
        self.previous_rusage = resource.getrusage(resource.RUSAGE_SELF)

        if gc.isenabled():
            self.previous_gc_count = gc.get_count()
        else:
            self.previous_gc_count = None

    def collect_metrics(self, **kwargs: Dict[str, Any]) -> List[Dict[str, Any]]:
        plugin_data = dict()
        try:
            plugin_data["name"] = "com.instana.plugin.python"
            plugin_data["entityId"] = str(os.getpid())
            plugin_data["data"] = DictionaryOfStan()

            if hasattr(self.collector.agent, "announce_data"):
                try:
                    plugin_data["data"]["pid"] = self.collector.agent.announce_data.pid
                except Exception:
                    plugin_data["data"]["pid"] = str(os.getpid())
            else:
                plugin_data["data"]["pid"] = str(os.getpid())

            with_snapshot = kwargs.get("with_snapshot", False)
            self._collect_runtime_metrics(plugin_data, with_snapshot)

            if with_snapshot:
                self._collect_runtime_snapshot(plugin_data)
        except Exception:
            logger.debug("_collect_metrics: ", exc_info=True)
        return [plugin_data]

    def _collect_runtime_metrics(
        self,
        plugin_data: Dict[str, Any],
        with_snapshot: bool,
    ) -> None:
        if os.environ.get("INSTANA_DISABLE_METRICS_COLLECTION", False):
            return

        """ Collect up and return the runtime metrics """
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            if gc.isenabled():
                self._collect_gc_metrics(plugin_data, with_snapshot)

            self._collect_thread_metrics(plugin_data, with_snapshot)

            value_diff = rusage.ru_utime - self.previous_rusage.ru_utime
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_utime",
                with_snapshot,
            )

            value_diff = rusage.ru_stime - self.previous_rusage.ru_stime
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_stime",
                with_snapshot,
            )

            self.apply_delta(
                rusage.ru_maxrss,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_maxrss",
                with_snapshot,
            )
            self.apply_delta(
                rusage.ru_ixrss,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_ixrss",
                with_snapshot,
            )
            self.apply_delta(
                rusage.ru_idrss,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_idrss",
                with_snapshot,
            )
            self.apply_delta(
                rusage.ru_isrss,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_isrss",
                with_snapshot,
            )

            value_diff = rusage.ru_minflt - self.previous_rusage.ru_minflt
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_minflt",
                with_snapshot,
            )

            value_diff = rusage.ru_majflt - self.previous_rusage.ru_majflt
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_majflt",
                with_snapshot,
            )

            value_diff = rusage.ru_nswap - self.previous_rusage.ru_nswap
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_nswap",
                with_snapshot,
            )

            value_diff = rusage.ru_inblock - self.previous_rusage.ru_inblock
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_inblock",
                with_snapshot,
            )

            value_diff = rusage.ru_oublock - self.previous_rusage.ru_oublock
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_oublock",
                with_snapshot,
            )

            value_diff = rusage.ru_msgsnd - self.previous_rusage.ru_msgsnd
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_msgsnd",
                with_snapshot,
            )

            value_diff = rusage.ru_msgrcv - self.previous_rusage.ru_msgrcv
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_msgrcv",
                with_snapshot,
            )

            value_diff = rusage.ru_nsignals - self.previous_rusage.ru_nsignals
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_nsignals",
                with_snapshot,
            )

            value_diff = rusage.ru_nvcsw - self.previous_rusage.ru_nvcsw
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_nvcsw",
                with_snapshot,
            )

            value_diff = rusage.ru_nivcsw - self.previous_rusage.ru_nivcsw
            self.apply_delta(
                value_diff,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "ru_nivcsw",
                with_snapshot,
            )
        except Exception:
            logger.debug("_collect_runtime_metrics", exc_info=True)
        finally:
            self.previous_rusage = rusage

    def _collect_gc_metrics(self, plugin_data, with_snapshot):
        try:
            gc_count = gc.get_count()
            gc_threshold = gc.get_threshold()

            self.apply_delta(
                gc_count[0],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "collect0",
                with_snapshot,
            )
            self.apply_delta(
                gc_count[1],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "collect1",
                with_snapshot,
            )
            self.apply_delta(
                gc_count[2],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "collect2",
                with_snapshot,
            )

            self.apply_delta(
                gc_threshold[0],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "threshold0",
                with_snapshot,
            )
            self.apply_delta(
                gc_threshold[1],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "threshold1",
                with_snapshot,
            )
            self.apply_delta(
                gc_threshold[2],
                self.previous["data"]["metrics"]["gc"],
                plugin_data["data"]["metrics"]["gc"],
                "threshold2",
                with_snapshot,
            )
        except Exception:
            logger.debug("_collect_gc_metrics", exc_info=True)

    def _collect_thread_metrics(
        self,
        plugin_data: Dict[str, Any],
        with_snapshot: bool,
    ) -> None:
        try:
            threads = threading.enumerate()
            daemon_threads = [thread.daemon is True for thread in threads].count(True)
            self.apply_delta(
                daemon_threads,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "daemon_threads",
                with_snapshot,
            )

            alive_threads = [thread.daemon is False for thread in threads].count(True)
            self.apply_delta(
                alive_threads,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "alive_threads",
                with_snapshot,
            )

            dummy_threads = [
                isinstance(thread, threading._DummyThread) for thread in threads
            ].count(True)  # pylint: disable=protected-access
            self.apply_delta(
                dummy_threads,
                self.previous["data"]["metrics"],
                plugin_data["data"]["metrics"],
                "dummy_threads",
                with_snapshot,
            )
        except Exception:
            logger.debug("_collect_thread_metrics", exc_info=True)

    def _collect_runtime_snapshot(
        self,
        plugin_data: Dict[str, Any],
    ) -> None:
        """Gathers Python specific Snapshot information for this process"""
        snapshot_payload = {}
        try:
            snapshot_payload["name"] = determine_service_name()
            snapshot_payload["version"] = sys.version
            snapshot_payload["f"] = platform.python_implementation()  # flavor
            snapshot_payload["a"] = platform.architecture()[0]  # architecture
            snapshot_payload["versions"] = self.gather_python_packages()
            snapshot_payload["iv"] = VERSION

            if is_autowrapt_instrumented():
                snapshot_payload["m"] = "Autowrapt"
            elif is_webhook_instrumented():
                snapshot_payload["m"] = "AutoTrace"
            else:
                snapshot_payload["m"] = "Manual"

            try:
                from django.conf import (
                    settings,  # pylint: disable=import-outside-toplevel
                )

                if hasattr(settings, "MIDDLEWARE") and settings.MIDDLEWARE is not None:
                    snapshot_payload["djmw"] = settings.MIDDLEWARE
                elif (
                    hasattr(settings, "MIDDLEWARE_CLASSES")
                    and settings.MIDDLEWARE_CLASSES is not None
                ):
                    snapshot_payload["djmw"] = settings.MIDDLEWARE_CLASSES
            except Exception:
                pass
        except Exception:
            logger.debug("collect_snapshot: ", exc_info=True)

        plugin_data["data"]["snapshot"] = snapshot_payload

    def gather_python_packages(self) -> Dict[str, Any]:
        """Collect up the list of modules in use"""
        if os.environ.get("INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION"):
            return {"instana": VERSION}

        versions = {}
        try:
            sys_packages = sys.modules.copy()

            for pkg_name in sys_packages:
                # Don't report submodules (e.g. django.x, django.y, django.z)
                # Skip modules that begin with underscore
                if ("." in pkg_name) or pkg_name[0] == "_":
                    continue

                # Skip builtins
                if pkg_name in ["sys", "curses"]:
                    continue

                if sys_packages[pkg_name]:
                    try:
                        pkg_info = sys_packages[pkg_name].__dict__
                        if "__version__" in pkg_info:
                            if isinstance(pkg_info["__version__"], str):
                                versions[pkg_name] = pkg_info["__version__"]
                            else:
                                versions[pkg_name] = self.jsonable(
                                    pkg_info["__version__"]
                                )
                        elif "version" in pkg_info:
                            versions[pkg_name] = self.jsonable(pkg_info["version"])
                        else:
                            versions[pkg_name] = importlib.metadata.version(pkg_name)
                    except importlib.metadata.PackageNotFoundError:
                        pass
                    except Exception:
                        logger.debug(
                            f"gather_python_packages: could not process module: {pkg_name}",
                        )

            # Manually set our package version
            versions["instana"] = VERSION
        except Exception:
            logger.debug("gather_python_packages", exc_info=True)

        return versions

    def jsonable(
        self,
        value: Union[Callable[[], Any], ModuleType, Any],
    ) -> str:
        try:
            if callable(value):
                try:
                    result = value()
                except Exception:
                    result = "Unknown"
            elif isinstance(value, ModuleType):
                result = value
            else:
                result = value
            return str(result)
        except Exception:
            logger.debug("jsonable: ", exc_info=True)
