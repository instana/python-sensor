# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

"""Collection helper for the Python runtime"""

import gc
import importlib.metadata
import os
import platform
import sys
import threading
from types import ModuleType
from typing import Any, Callable, Optional, Union

from instana.collector.base import BaseCollector
from instana.collector.helpers.base import BaseHelper
from instana.collector.helpers.resource_usage import get_resource_usage
from instana.log import logger
from instana.util import DictionaryOfStan
from instana.util.runtime import determine_service_name
from instana.version import VERSION

PATH_OF_DEPRECATED_INSTALLATION_VIA_HOST_AGENT = "/tmp/.instana/python"

PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR = "/opt/instana/instrumentation/python/"


def is_autowrapt_instrumented() -> bool:
    return "instana" in os.environ.get("AUTOWRAPT_BOOTSTRAP", ())


def is_webhook_instrumented() -> bool:
    return any(PATH_OF_AUTOTRACE_WEBHOOK_SITEDIR in p for p in sys.path)


class RuntimeHelper(BaseHelper):
    """Helper class to collect snapshot and metrics for this Python runtime"""

    def __init__(
        self,
        collector: BaseCollector,
    ) -> None:
        super(RuntimeHelper, self).__init__(collector)
        self.previous = DictionaryOfStan()
        self.previous_rusage = get_resource_usage()

        gc_enabled = gc.isenabled()
        self.previous_gc_count = gc.get_count() if gc_enabled else None

    def collect_metrics(self, **kwargs: Any) -> list[dict[str, Any]]:
        plugin_data = {}
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
        plugin_data: dict[str, Any],
        with_snapshot: bool,
    ) -> None:
        """Collect and report runtime resource-usage metrics."""
        if os.environ.get("INSTANA_DISABLE_METRICS_COLLECTION", False):
            return

        rusage = get_resource_usage()
        prev = self.previous_rusage
        try:
            if gc.isenabled():
                self._collect_gc_metrics(plugin_data, with_snapshot)

            self._collect_thread_metrics(plugin_data, with_snapshot)

            pm = self.previous["data"]["metrics"]
            nm = plugin_data["data"]["metrics"]
            # Delta (counter) fields — direct attribute access avoids getattr overhead
            self.apply_delta(
                rusage.ru_utime - prev.ru_utime, pm, nm, "ru_utime", with_snapshot
            )
            self.apply_delta(
                rusage.ru_stime - prev.ru_stime, pm, nm, "ru_stime", with_snapshot
            )
            self.apply_delta(
                rusage.ru_minflt - prev.ru_minflt, pm, nm, "ru_minflt", with_snapshot
            )
            self.apply_delta(
                rusage.ru_majflt - prev.ru_majflt, pm, nm, "ru_majflt", with_snapshot
            )
            self.apply_delta(
                rusage.ru_nswap - prev.ru_nswap, pm, nm, "ru_nswap", with_snapshot
            )
            self.apply_delta(
                rusage.ru_inblock - prev.ru_inblock, pm, nm, "ru_inblock", with_snapshot
            )
            self.apply_delta(
                rusage.ru_oublock - prev.ru_oublock, pm, nm, "ru_oublock", with_snapshot
            )
            self.apply_delta(
                rusage.ru_msgsnd - prev.ru_msgsnd, pm, nm, "ru_msgsnd", with_snapshot
            )
            self.apply_delta(
                rusage.ru_msgrcv - prev.ru_msgrcv, pm, nm, "ru_msgrcv", with_snapshot
            )
            self.apply_delta(
                rusage.ru_nsignals - prev.ru_nsignals,
                pm,
                nm,
                "ru_nsignals",
                with_snapshot,
            )
            self.apply_delta(
                rusage.ru_nvcsw - prev.ru_nvcsw, pm, nm, "ru_nvcsw", with_snapshot
            )
            self.apply_delta(
                rusage.ru_nivcsw - prev.ru_nivcsw, pm, nm, "ru_nivcsw", with_snapshot
            )
            # Absolute (gauge) fields
            self.apply_delta(rusage.ru_maxrss, pm, nm, "ru_maxrss", with_snapshot)
            self.apply_delta(rusage.ru_ixrss, pm, nm, "ru_ixrss", with_snapshot)
            self.apply_delta(rusage.ru_idrss, pm, nm, "ru_idrss", with_snapshot)
            self.apply_delta(rusage.ru_isrss, pm, nm, "ru_isrss", with_snapshot)
        except Exception:
            logger.debug("_collect_runtime_metrics", exc_info=True)
        finally:
            self.previous_rusage = rusage

    def _collect_gc_metrics(
        self,
        plugin_data: dict[str, Any],
        with_snapshot: bool,
    ) -> None:
        try:
            gc_count = gc.get_count()
            gc_threshold = gc.get_threshold()

            gc_metrics = {
                "collect0": gc_count[0],
                "collect1": gc_count[1],
                "collect2": gc_count[2],
                "threshold0": gc_threshold[0],
                "threshold1": gc_threshold[1],
                "threshold2": gc_threshold[2],
            }
            prev_gc = self.previous["data"]["metrics"]["gc"]
            new_gc = plugin_data["data"]["metrics"]["gc"]
            for metric, value in gc_metrics.items():
                self.apply_delta(value, prev_gc, new_gc, metric, with_snapshot)
        except Exception:
            logger.debug("_collect_gc_metrics", exc_info=True)

    def _collect_thread_metrics(
        self,
        plugin_data: dict[str, Any],
        with_snapshot: bool,
    ) -> None:
        try:
            threads = threading.enumerate()
            # Single pass: avoids three separate list-comprehensions and a
            # temporary dict, which is the fastest approach for small lists.
            daemon = alive = dummy = 0
            for t in threads:
                if isinstance(t, threading._DummyThread):  # pylint: disable=protected-access
                    dummy += 1
                elif t.daemon:
                    daemon += 1
                else:
                    alive += 1
            prev_metrics = self.previous["data"]["metrics"]
            new_metrics = plugin_data["data"]["metrics"]
            self.apply_delta(
                daemon, prev_metrics, new_metrics, "daemon_threads", with_snapshot
            )
            self.apply_delta(
                alive, prev_metrics, new_metrics, "alive_threads", with_snapshot
            )
            self.apply_delta(
                dummy, prev_metrics, new_metrics, "dummy_threads", with_snapshot
            )
        except Exception:
            logger.debug("_collect_thread_metrics", exc_info=True)

    def _collect_runtime_snapshot(
        self,
        plugin_data: dict[str, Any],
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
                logger.debug(
                    "_collect_runtime_snapshot: django settings unavailable",
                    exc_info=True,
                )
        except Exception:
            logger.debug("collect_snapshot: ", exc_info=True)

        plugin_data["data"]["snapshot"] = snapshot_payload

    def _resolve_package_version(
        self, pkg_name: str, module: ModuleType
    ) -> Optional[str]:
        """Return the version string for a single module, or None if undiscoverable.

        Args:
            pkg_name: The top-level package name (e.g. "django").
            module: The module object from sys.modules.

        Returns:
            A version string, or None when the version cannot be determined.
        """
        try:
            pkg_info = module.__dict__
            if "__version__" in pkg_info:
                v = pkg_info["__version__"]
                return v if isinstance(v, str) else self.jsonable(v)
            if "version" in pkg_info:
                return self.jsonable(pkg_info["version"])
            return importlib.metadata.version(pkg_name)
        except importlib.metadata.PackageNotFoundError:
            return None
        except Exception:
            logger.debug(
                f"gather_python_packages: could not process module: {pkg_name}",
            )
            return None

    def gather_python_packages(self) -> dict[str, str]:
        """Collect up the list of modules in use."""
        if os.environ.get("INSTANA_DISABLE_PYTHON_PACKAGE_COLLECTION"):
            return {"instana": VERSION}

        versions = {}
        try:
            sys_packages = sys.modules.copy()

            for pkg_name, module in sys_packages.items():
                # Don't report submodules (e.g. django.x, django.y, django.z)
                # Skip modules that begin with underscore
                if ("." in pkg_name) or pkg_name.startswith("_"):
                    continue

                # Skip builtins
                if pkg_name in ["sys", "curses"]:
                    continue

                if module:
                    version = self._resolve_package_version(pkg_name, module)
                    if version is not None:
                        versions[pkg_name] = version

            # Manually set our package version
            versions["instana"] = VERSION
        except Exception:
            logger.debug("gather_python_packages", exc_info=True)

        return versions

    def jsonable(
        self,
        value: Union[Callable[[], str], ModuleType, object],
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
            return ""
