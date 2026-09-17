# (c) Copyright IBM Corp. 2026
from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from instana import _defer_boot_until_eventlet_patch


class TestEventletDeferredBoot:
    @pytest.fixture(autouse=True)
    def setup_environment(self) -> Generator[None, None, None]:
        """Setup and teardown environment around tests."""
        yield
        os.environ.pop("INSTANA_AUTOPROFILE", None)

    def test_defer_boot_registers_wrapper(self) -> None:
        """Verify that _defer_boot_until_eventlet_patch registers a wrapt wrapper on eventlet.monkey_patch."""
        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            _defer_boot_until_eventlet_patch()
            mock_wrap.assert_called_once()
            args, _ = mock_wrap.call_args
            assert args[0] == "eventlet"
            assert args[1] == "monkey_patch"

    def test_after_monkey_patch_in_worker_process(self) -> None:
        """When running in a worker process (ppid cmdline contains 'gunicorn'), boot_agent is called."""
        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            _defer_boot_until_eventlet_patch()
            wrapper = mock_wrap.call_args[0][2]

        mock_wrapped = MagicMock(return_value="patched")
        mock_open = patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"gunicorn: master [app]"))), __exit__=MagicMock(return_value=False))))

        with mock_open, patch("instana.boot_agent") as mock_boot:
            result = wrapper(mock_wrapped, None, (), {})
            assert result == "patched"
            mock_wrapped.assert_called_once_with()
            mock_boot.assert_called_once()

    def test_after_monkey_patch_in_arbiter_process(self) -> None:
        """When not running in a worker process (ppid cmdline does not contain 'gunicorn'), boot_agent is NOT called."""
        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            _defer_boot_until_eventlet_patch()
            wrapper = mock_wrap.call_args[0][2]

        mock_wrapped = MagicMock(return_value="patched")
        mock_open = patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"bash -i"))), __exit__=MagicMock(return_value=False))))

        with mock_open, patch("instana.boot_agent") as mock_boot:
            result = wrapper(mock_wrapped, None, (), {})
            assert result == "patched"
            mock_wrapped.assert_called_once_with()
            mock_boot.assert_not_called()

    def test_after_monkey_patch_oserror_non_linux(self) -> None:
        """When /proc/{ppid}/cmdline raises OSError (e.g., macOS or PID 1), boot_agent is NOT called."""
        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            _defer_boot_until_eventlet_patch()
            wrapper = mock_wrap.call_args[0][2]

        mock_wrapped = MagicMock(return_value="patched")

        def raise_oserror(*args: object, **kwargs: object) -> None:
            raise OSError("No such file or directory")

        with patch("builtins.open", side_effect=raise_oserror), patch("instana.boot_agent") as mock_boot:
            result = wrapper(mock_wrapped, None, (), {})
            assert result == "patched"
            mock_wrapped.assert_called_once_with()
            mock_boot.assert_not_called()

    def test_after_monkey_patch_with_autoprofile(self) -> None:
        """When INSTANA_AUTOPROFILE is set and in worker process, _start_profiler is called before boot_agent."""
        os.environ["INSTANA_AUTOPROFILE"] = "true"

        with patch("wrapt.wrap_function_wrapper") as mock_wrap:
            _defer_boot_until_eventlet_patch()
            wrapper = mock_wrap.call_args[0][2]

        mock_wrapped = MagicMock(return_value=None)
        mock_open = patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=b"gunicorn: master [app]"))), __exit__=MagicMock(return_value=False))))

        with mock_open, patch("instana._start_profiler") as mock_profiler, patch("instana.boot_agent") as mock_boot:
            result = wrapper(mock_wrapped, None, (), {})
            assert result is None
            mock_profiler.assert_called_once()
            mock_boot.assert_called_once()
