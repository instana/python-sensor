# (c) Copyright IBM Corp. 2026
from __future__ import annotations

import os
import sys
import types
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

import instana
from instana import _defer_boot_until_eventlet_patch


def _make_fake_geventlet_module() -> types.ModuleType:
    """Return a minimal fake gunicorn.workers.geventlet module with EventletWorker.patch."""

    class EventletWorker:
        def patch(self) -> None:
            pass

    mod = types.ModuleType("gunicorn.workers.geventlet")
    mod.EventletWorker = EventletWorker  # type: ignore[attr-defined]
    return mod


def _make_fake_eventlet_module() -> types.ModuleType:
    """Return a minimal fake eventlet module with monkey_patch."""

    mod = types.ModuleType("eventlet")

    def monkey_patch(*args: object, **kwargs: object) -> None:
        pass

    mod.monkey_patch = monkey_patch  # type: ignore[attr-defined]
    return mod


# ---------------------------------------------------------------------------
# Helper: register both hooks and return captured callbacks
# ---------------------------------------------------------------------------

def _register_hooks() -> tuple[list[tuple[str, object]], list[MagicMock]]:
    """Call _defer_boot_until_eventlet_patch() and capture the two when_imported callbacks.

    Returns
    -------
    callbacks : list of (module_name, callback_fn) pairs — one per registered hook
    wrap_calls : list of MagicMock wrap_function_wrapper call recorders (empty at this point)
    """
    captured: list[tuple[str, object]] = []

    def fake_when_imported(name: str):
        def decorator(fn: object) -> object:
            captured.append((name, fn))
            return fn
        return decorator

    with patch("wrapt.when_imported", side_effect=fake_when_imported):
        _defer_boot_until_eventlet_patch()

    return captured, []


class TestDeferredBootHookRegistration:
    """Both hooks are always registered, regardless of whether gunicorn is installed."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> Generator[None, None, None]:
        instana._eventlet_booted = False
        yield
        instana._eventlet_booted = False

    def test_both_hooks_always_registered(self) -> None:
        """when_imported is called for both gunicorn.workers.geventlet and eventlet."""
        callbacks, _ = _register_hooks()
        names = [name for name, _ in callbacks]
        assert "gunicorn.workers.geventlet" in names
        assert "eventlet" in names

    def test_hook_registration_does_not_import_ssl_touching_modules(self) -> None:
        """Registering the hooks must not pull urllib3 or requests into sys.modules."""
        ssl_mods = ("urllib3", "requests")
        before = {m for m in ssl_mods if m in sys.modules}

        with patch("wrapt.when_imported", return_value=lambda fn: fn):
            _defer_boot_until_eventlet_patch()

        after = {m for m in ssl_mods if m in sys.modules}
        newly_imported = after - before
        assert newly_imported == set(), (
            f"_defer_boot_until_eventlet_patch() imported ssl-touching modules: "
            f"{newly_imported}. These must remain unimported until after "
            f"eventlet.monkey_patch() to avoid the SSLContext RecursionError."
        )


class TestGunicornEventletWorkerHook:
    """Hook 1: gunicorn.workers.geventlet — boots in the worker, after monkey_patch()."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> Generator[None, None, None]:
        instana._eventlet_booted = False
        yield
        instana._eventlet_booted = False
        os.environ.pop("INSTANA_AUTOPROFILE", None)

    def _get_geventlet_callback(self) -> object:
        callbacks, _ = _register_hooks()
        return next(fn for name, fn in callbacks if name == "gunicorn.workers.geventlet")

    def test_wraps_eventlet_worker_patch(self) -> None:
        """When geventlet is imported, wrap_function_wrapper targets EventletWorker.patch."""
        cb = self._get_geventlet_callback()
        fake_mod = _make_fake_geventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        args, _ = mock_wrap.call_args
        assert args[0] is fake_mod
        assert args[1] == "EventletWorker.patch"

    def test_worker_patch_wrapper_boots_agent(self) -> None:
        """The wrapper calls boot_agent() after the original patch()."""
        cb = self._get_geventlet_callback()
        fake_mod = _make_fake_geventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        wrapper = mock_wrap.call_args[0][2]
        mock_wrapped = MagicMock(return_value=None)

        with patch("instana.boot_agent") as mock_boot:
            wrapper(mock_wrapped, None, (), {})
            mock_wrapped.assert_called_once_with()
            mock_boot.assert_called_once()

    def test_worker_patch_wrapper_returns_result(self) -> None:
        """The wrapper passes through the return value of the original patch()."""
        cb = self._get_geventlet_callback()
        fake_mod = _make_fake_geventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        wrapper = mock_wrap.call_args[0][2]
        mock_wrapped = MagicMock(return_value="sentinel")

        with patch("instana.boot_agent"):
            result = wrapper(mock_wrapped, None, (), {})

        assert result == "sentinel"

    def test_double_boot_protection(self) -> None:
        """EventletWorker.patch() called twice → boot_agent() called only once."""
        cb = self._get_geventlet_callback()
        fake_mod = _make_fake_geventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        wrapper = mock_wrap.call_args[0][2]
        mock_wrapped = MagicMock(return_value=None)

        with patch("instana.boot_agent") as mock_boot:
            wrapper(mock_wrapped, None, (), {})
            wrapper(mock_wrapped, None, (), {})
            mock_boot.assert_called_once()

    def test_autoprofile_started_before_boot_agent(self) -> None:
        """INSTANA_AUTOPROFILE=true: profiler starts before boot_agent in worker."""
        os.environ["INSTANA_AUTOPROFILE"] = "true"
        cb = self._get_geventlet_callback()
        fake_mod = _make_fake_geventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        wrapper = mock_wrap.call_args[0][2]
        call_order: list[str] = []

        with (
            patch("instana._start_profiler", side_effect=lambda: call_order.append("profiler")),
            patch("instana.boot_agent", side_effect=lambda: call_order.append("boot")),
        ):
            wrapper(MagicMock(return_value=None), None, (), {})

        assert call_order == ["profiler", "boot"]

    def test_gunicorn26_no_crash_when_geventlet_never_imported(self) -> None:
        """Gunicorn ≥26 removed geventlet. when_imported never fires → no error."""
        # Simulate: hook is registered but the module is never imported.
        # Registering is enough — nothing should raise.
        with patch("wrapt.when_imported", return_value=lambda fn: fn):
            _defer_boot_until_eventlet_patch()  # must not raise


class TestBareMonkeyPatchHook:
    """Hook 2: eventlet.monkey_patch — bare application and gunicorn ≥26."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> Generator[None, None, None]:
        instana._eventlet_booted = False
        yield
        instana._eventlet_booted = False
        os.environ.pop("INSTANA_AUTOPROFILE", None)
        # Ensure geventlet is not in sys.modules between tests
        sys.modules.pop("gunicorn.workers.geventlet", None)

    def _get_eventlet_callback_and_wrapper(self) -> object:
        callbacks, _ = _register_hooks()
        cb = next(fn for name, fn in callbacks if name == "eventlet")
        fake_mod = _make_fake_eventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        return mock_wrap.call_args[0][2]

    def test_wraps_monkey_patch_on_eventlet_module(self) -> None:
        """When eventlet is imported, wrap_function_wrapper targets eventlet.monkey_patch."""
        callbacks, _ = _register_hooks()
        cb = next(fn for name, fn in callbacks if name == "eventlet")
        fake_mod = _make_fake_eventlet_module()

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            cb(fake_mod)

        args, _ = mock_wrap.call_args
        assert args[0] is fake_mod
        assert args[1] == "monkey_patch"

    def test_boots_agent_when_geventlet_not_in_sys_modules(self) -> None:
        """Without gunicorn.workers.geventlet in sys.modules, boot_agent() is called."""
        assert "gunicorn.workers.geventlet" not in sys.modules
        wrapper = self._get_eventlet_callback_and_wrapper()
        mock_wrapped = MagicMock(return_value="patched")

        with patch("instana.boot_agent") as mock_boot:
            result = wrapper(mock_wrapped, None, (), {})

        assert result == "patched"
        mock_boot.assert_called_once()

    def test_skips_boot_when_geventlet_in_sys_modules(self) -> None:
        """With gunicorn.workers.geventlet present, arbiter-side boot is skipped."""
        sys.modules["gunicorn.workers.geventlet"] = _make_fake_geventlet_module()
        wrapper = self._get_eventlet_callback_and_wrapper()
        mock_wrapped = MagicMock(return_value=None)

        with patch("instana.boot_agent") as mock_boot:
            wrapper(mock_wrapped, None, (), {})
            mock_boot.assert_not_called()

    def test_double_boot_protection(self) -> None:
        """monkey_patch() called twice without gunicorn → boot_agent() called only once."""
        assert "gunicorn.workers.geventlet" not in sys.modules
        wrapper = self._get_eventlet_callback_and_wrapper()
        mock_wrapped = MagicMock(return_value=None)

        with patch("instana.boot_agent") as mock_boot:
            wrapper(mock_wrapped, None, (), {})
            wrapper(mock_wrapped, None, (), {})
            mock_boot.assert_called_once()

    def test_autoprofile_started_before_boot_agent(self) -> None:
        """INSTANA_AUTOPROFILE=true in fallback path: profiler starts before boot_agent."""
        os.environ["INSTANA_AUTOPROFILE"] = "true"
        assert "gunicorn.workers.geventlet" not in sys.modules
        wrapper = self._get_eventlet_callback_and_wrapper()
        call_order: list[str] = []

        with (
            patch("instana._start_profiler", side_effect=lambda: call_order.append("profiler")),
            patch("instana.boot_agent", side_effect=lambda: call_order.append("boot")),
        ):
            wrapper(MagicMock(return_value=None), None, (), {})

        assert call_order == ["profiler", "boot"]


class TestEventletDeferredBootModuleTopLevel:
    """Module-level opt-in dispatch: INSTANA_EVENTLET_DEFERRED_BOOT flag behaviour."""

    @pytest.fixture(autouse=True)
    def _clean_env(self) -> Generator[None, None, None]:
        instana._eventlet_booted = False
        yield
        instana._eventlet_booted = False
        for key in ("INSTANA_EVENTLET_DEFERRED_BOOT", "INSTANA_AUTOPROFILE"):
            os.environ.pop(key, None)

    def _run_toplevel_boot(
        self,
        *,
        eventlet_installed: bool,
        deferred_flag: str | None,
    ) -> tuple[MagicMock, MagicMock]:
        """Simulate the module-level dispatch block with controlled environment."""
        env_patch: dict[str, str] = {}
        if deferred_flag is not None:
            env_patch["INSTANA_EVENTLET_DEFERRED_BOOT"] = deferred_flag

        find_spec_return = object() if eventlet_installed else None

        with (
            patch.dict(os.environ, env_patch, clear=False),
            patch("instana.importlib_util.find_spec", return_value=find_spec_return),
            patch("instana._defer_boot_until_eventlet_patch") as mock_defer,
            patch("instana.boot_agent") as mock_boot,
            patch("instana.is_autowrapt_instrumented", return_value=True),
            patch("instana.is_webhook_instrumented", return_value=False),
        ):
            auto_instr_on = "INSTANA_DISABLE_AUTO_INSTR" not in os.environ
            if auto_instr_on:
                eventlet_spec = instana.importlib_util.find_spec("eventlet")
                deferred = bool(eventlet_spec) and instana.is_truthy(
                    os.environ.get("INSTANA_EVENTLET_DEFERRED_BOOT", None)
                )
                if deferred:
                    instana._defer_boot_until_eventlet_patch()
                    return_early = True
                else:
                    return_early = False
            else:
                return_early = False

            if not return_early:
                instana.boot_agent()

        return mock_defer, mock_boot

    def test_no_flag_boots_immediately(self) -> None:
        """Without INSTANA_EVENTLET_DEFERRED_BOOT, boot_agent() is called immediately."""
        mock_defer, mock_boot = self._run_toplevel_boot(
            eventlet_installed=True,
            deferred_flag=None,
        )
        mock_boot.assert_called_once()
        mock_defer.assert_not_called()

    def test_flag_true_no_eventlet_boots_immediately(self) -> None:
        """Flag is set but eventlet not installed → normal boot, no deferral."""
        mock_defer, mock_boot = self._run_toplevel_boot(
            eventlet_installed=False,
            deferred_flag="true",
        )
        mock_boot.assert_called_once()
        mock_defer.assert_not_called()

    def test_flag_false_with_eventlet_boots_immediately(self) -> None:
        """Flag explicitly false with eventlet installed → normal boot."""
        mock_defer, mock_boot = self._run_toplevel_boot(
            eventlet_installed=True,
            deferred_flag="false",
        )
        mock_boot.assert_called_once()
        mock_defer.assert_not_called()

    def test_flag_true_with_eventlet_defers_boot(self) -> None:
        """Flag true + eventlet installed → _defer_boot_until_eventlet_patch() called, boot_agent() NOT called."""
        mock_defer, mock_boot = self._run_toplevel_boot(
            eventlet_installed=True,
            deferred_flag="true",
        )
        mock_defer.assert_called_once()
        mock_boot.assert_not_called()
