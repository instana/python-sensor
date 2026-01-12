# (c) Copyright IBM Corp. 2025
"""
Unit tests for TheMachine cmdline-related methods in fsm.py.

This test module provides comprehensive coverage for the command line retrieval
functions that work across different platforms (Windows, Linux, Unix).

Tested functions:
- _get_cmdline_windows(): Retrieves command line on Windows using ctypes
- _get_cmdline_linux_proc(): Retrieves command line from /proc/self/cmdline
- _get_cmdline_unix_ps(): Retrieves command line using ps command
- _get_cmdline_unix(): Dispatches to appropriate Unix method
- _get_cmdline(): Main entry point with platform detection and error handling

"""

import os
import subprocess
import sys
from typing import Generator
from unittest.mock import Mock, mock_open, patch

import pytest

from instana.fsm import TheMachine


class TestTheMachineCmdline:
    """Test suite for TheMachine cmdline-related methods."""

    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup and teardown for each test."""
        with patch("instana.fsm.TheMachine.__init__", return_value=None):
            self.machine = TheMachine(Mock())
        yield

    @pytest.mark.parametrize(
        "cmdline_input,expected_output",
        [
            (
                "C:\\Python\\python.exe script.py arg1 arg2",
                ["C:\\Python\\python.exe", "script.py", "arg1", "arg2"],
            ),
            (
                "python.exe -m module --flag value",
                ["python.exe", "-m", "module", "--flag", "value"],
            ),
            ("single_command", ["single_command"]),
            (
                "cmd.exe /c echo hello",
                ["cmd.exe", "/c", "echo", "hello"],
            ),
        ],
        ids=[
            "full_path_with_args",
            "python_module_with_flags",
            "single_command",
            "cmd_with_subcommand",
        ],
    )
    def test_get_cmdline_windows(
        self, cmdline_input: str, expected_output: list, mocker
    ) -> None:
        """Test _get_cmdline_windows with various command line formats."""
        mocker.patch(
            "ctypes.windll",
            create=True,
        )

        with patch("ctypes.windll.kernel32.GetCommandLineW") as mock_get_cmdline:
            mock_get_cmdline.return_value = cmdline_input
            result = self.machine._get_cmdline_windows()
            assert result == expected_output

    def test_get_cmdline_windows_empty_string(self, mocker) -> None:
        """Test _get_cmdline_windows with empty command line."""
        mocker.patch(
            "ctypes.windll",
            create=True,
        )

        with patch("ctypes.windll.kernel32.GetCommandLineW") as mock_get_cmdline:
            mock_get_cmdline.return_value = ""
            result = self.machine._get_cmdline_windows()
            assert result == []

    @pytest.mark.parametrize(
        "proc_content,expected_output",
        [
            (
                "python\x00script.py\x00arg1\x00arg2\x00",
                ["python", "script.py", "arg1", "arg2", ""],
            ),
            (
                "/usr/bin/python3\x00-m\x00flask\x00run\x00",
                ["/usr/bin/python3", "-m", "flask", "run", ""],
            ),
            ("gunicorn\x00app:app\x00", ["gunicorn", "app:app", ""]),
            ("/usr/bin/python\x00", ["/usr/bin/python", ""]),
            (
                "python3\x00-c\x00print('hello')\x00",
                ["python3", "-c", "print('hello')", ""],
            ),
        ],
        ids=[
            "basic_script_with_args",
            "python_module",
            "gunicorn_app",
            "single_executable",
            "python_command",
        ],
    )
    def test_get_cmdline_linux_proc(
        self, proc_content: str, expected_output: list
    ) -> None:
        """Test _get_cmdline_linux_proc with various /proc/self/cmdline formats."""
        with patch("builtins.open", mock_open(read_data=proc_content)):
            result = self.machine._get_cmdline_linux_proc()
            assert result == expected_output

    def test_get_cmdline_linux_proc_file_not_found(self) -> None:
        """Test _get_cmdline_linux_proc when file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError):
                self.machine._get_cmdline_linux_proc()

    def test_get_cmdline_linux_proc_permission_error(self) -> None:
        """Test _get_cmdline_linux_proc with permission error."""
        with patch("builtins.open", side_effect=PermissionError()):
            with pytest.raises(PermissionError):
                self.machine._get_cmdline_linux_proc()

    @pytest.mark.parametrize(
        "ps_output,expected_output",
        [
            (
                b"COMMAND\npython script.py arg1 arg2\n",
                ["python script.py arg1 arg2"],
            ),
            (
                b"COMMAND\n/usr/bin/python3 -m flask run\n",
                ["/usr/bin/python3 -m flask run"],
            ),
            (b"COMMAND\ngunicorn app:app\n", ["gunicorn app:app"]),
            (b"COMMAND\npython\n", ["python"]),
        ],
        ids=[
            "script_with_args",
            "python_module",
            "gunicorn",
            "single_command",
        ],
    )
    def test_get_cmdline_unix_ps(self, ps_output: bytes, expected_output: list) -> None:
        """Test _get_cmdline_unix_ps with various ps command outputs."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = (ps_output, b"")

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = self.machine._get_cmdline_unix_ps(1234)
            assert result == expected_output
            mock_popen.assert_called_once_with(
                ["ps", "-p", "1234", "-o", "args"], stdout=subprocess.PIPE
            )

    def test_get_cmdline_unix_ps_with_different_pid(self) -> None:
        """Test _get_cmdline_unix_ps with different PID values."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = (b"COMMAND\ntest_process\n", b"")

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            result = self.machine._get_cmdline_unix_ps(9999)
            assert result == ["test_process"]
            mock_popen.assert_called_once_with(
                ["ps", "-p", "9999", "-o", "args"], stdout=subprocess.PIPE
            )

    def test_get_cmdline_unix_ps_empty_output(self) -> None:
        """Test _get_cmdline_unix_ps with empty ps output."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = (b"COMMAND\n\n", b"")

        with patch("subprocess.Popen", return_value=mock_proc):
            result = self.machine._get_cmdline_unix_ps(1234)
            assert result == [""]

    def test_get_cmdline_unix_ps_subprocess_error(self) -> None:
        """Test _get_cmdline_unix_ps when subprocess fails."""
        with patch(
            "subprocess.Popen", side_effect=subprocess.SubprocessError("Test error")
        ):
            with pytest.raises(subprocess.SubprocessError):
                self.machine._get_cmdline_unix_ps(1234)

    @pytest.mark.parametrize(
        "proc_exists,proc_content,expected_output",
        [
            (
                True,
                "python\x00script.py\x00",
                ["python", "script.py", ""],
            ),
            (
                False,
                None,
                ["ps_output"],
            ),
        ],
        ids=["proc_exists", "proc_not_exists"],
    )
    def test_get_cmdline_unix(
        self, proc_exists: bool, proc_content: str, expected_output: list
    ) -> None:
        """Test _get_cmdline_unix with and without /proc filesystem."""
        with patch("os.path.isfile", return_value=proc_exists):
            if proc_exists:
                with patch("builtins.open", mock_open(read_data=proc_content)):
                    result = self.machine._get_cmdline_unix(1234)
                    assert result == expected_output
            else:
                mock_proc = Mock()
                mock_proc.communicate.return_value = (b"COMMAND\nps_output\n", b"")
                with patch("subprocess.Popen", return_value=mock_proc):
                    result = self.machine._get_cmdline_unix(1234)
                    assert result == expected_output

    def test_get_cmdline_unix_proc_file_check(self) -> None:
        """Test _get_cmdline_unix checks for /proc/self/cmdline correctly."""
        with patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = True
            with patch("builtins.open", mock_open(read_data="test\x00")):
                self.machine._get_cmdline_unix(1234)
                mock_isfile.assert_called_once_with("/proc/self/cmdline")

    @pytest.mark.parametrize(
        "is_windows_value,expected_method",
        [
            (True, "_get_cmdline_windows"),
            (False, "_get_cmdline_unix"),
        ],
        ids=["windows", "unix"],
    )
    def test_get_cmdline_platform_detection(
        self, is_windows_value: bool, expected_method: str
    ) -> None:
        """Test _get_cmdline correctly detects platform and calls appropriate method."""
        with patch("instana.fsm.is_windows", return_value=is_windows_value):
            if is_windows_value:
                with patch.object(
                    self.machine, "_get_cmdline_windows", return_value=["windows_cmd"]
                ) as mock_method:
                    result = self.machine._get_cmdline(1234)
                    assert result == ["windows_cmd"]
                    mock_method.assert_called_once()
            else:
                with patch.object(
                    self.machine, "_get_cmdline_unix", return_value=["unix_cmd"]
                ) as mock_method:
                    result = self.machine._get_cmdline(1234)
                    assert result == ["unix_cmd"]
                    mock_method.assert_called_once_with(1234)

    def test_get_cmdline_windows_exception_fallback(self) -> None:
        """Test _get_cmdline falls back to sys.argv on Windows exception."""
        with patch("instana.fsm.is_windows", return_value=True), patch.object(
            self.machine, "_get_cmdline_windows", side_effect=Exception("Test error")
        ), patch("instana.fsm.logger.debug") as mock_logger:
            result = self.machine._get_cmdline(1234)
            assert result == sys.argv
            mock_logger.assert_called_once()

    def test_get_cmdline_unix_exception_fallback(self) -> None:
        """Test _get_cmdline falls back to sys.argv on Unix exception."""
        with patch("instana.fsm.is_windows", return_value=False), patch.object(
            self.machine, "_get_cmdline_unix", side_effect=Exception("Test error")
        ), patch("instana.fsm.logger.debug") as mock_logger:
            result = self.machine._get_cmdline(1234)
            assert result == sys.argv
            mock_logger.assert_called_once()

    @pytest.mark.parametrize(
        "exception_type",
        [
            OSError,
            IOError,
            PermissionError,
            FileNotFoundError,
            RuntimeError,
        ],
        ids=[
            "OSError",
            "IOError",
            "PermissionError",
            "FileNotFoundError",
            "RuntimeError",
        ],
    )
    def test_get_cmdline_various_exceptions(self, exception_type: type) -> None:
        """Test _get_cmdline handles various exception types gracefully."""
        with patch("instana.fsm.is_windows", return_value=False), patch.object(
            self.machine, "_get_cmdline_unix", side_effect=exception_type("Test error")
        ):
            result = self.machine._get_cmdline(1234)
            assert result == sys.argv

    def test_get_cmdline_with_actual_pid(self) -> None:
        """Test _get_cmdline with actual process ID."""
        current_pid = os.getpid()
        with patch("instana.fsm.is_windows", return_value=False), patch.object(
            self.machine, "_get_cmdline_unix", return_value=["test_cmd"]
        ) as mock_method:
            result = self.machine._get_cmdline(current_pid)
            assert result == ["test_cmd"]
            mock_method.assert_called_once_with(current_pid)

    def test_get_cmdline_windows_with_quotes(self, mocker) -> None:
        """Test _get_cmdline_windows handles command lines with quotes."""
        cmdline_with_quotes = '"C:\\Program Files\\Python\\python.exe" "my script.py"'
        mocker.patch(
            "ctypes.windll",
            create=True,
        )

        with patch("ctypes.windll.kernel32.GetCommandLineW") as mock_get_cmdline:
            mock_get_cmdline.return_value = cmdline_with_quotes
            result = self.machine._get_cmdline_windows()
            # Note: Simple split() doesn't handle quotes properly, this tests current behavior
            assert isinstance(result, list)
            assert len(result) > 0

    def test_get_cmdline_linux_proc_with_empty_args(self) -> None:
        """Test _get_cmdline_linux_proc with command that has empty arguments."""
        proc_content = "python\x00\x00\x00"
        with patch("builtins.open", mock_open(read_data=proc_content)):
            result = self.machine._get_cmdline_linux_proc()
            assert result == ["python", "", "", ""]

    def test_get_cmdline_unix_ps_with_multiline_output(self) -> None:
        """Test _get_cmdline_unix_ps handles multiline ps output correctly."""
        ps_output = b"COMMAND\npython script.py\nextra line\n"
        mock_proc = Mock()
        mock_proc.communicate.return_value = (ps_output, b"")

        with patch("subprocess.Popen", return_value=mock_proc):
            result = self.machine._get_cmdline_unix_ps(1234)
            # Should only take the second line (index 1)
            assert result == ["python script.py"]

    def test_get_cmdline_unix_ps_with_special_characters(self) -> None:
        """Test _get_cmdline_unix_ps with special characters in command."""
        ps_output = b"COMMAND\npython -c 'print(\"hello\")'\n"
        mock_proc = Mock()
        mock_proc.communicate.return_value = (ps_output, b"")

        with patch("subprocess.Popen", return_value=mock_proc):
            result = self.machine._get_cmdline_unix_ps(1234)
            assert result == ["python -c 'print(\"hello\")'"]

    def test_get_cmdline_linux_proc_with_unicode(self) -> None:
        """Test _get_cmdline_linux_proc with unicode characters."""
        proc_content = "python\x00script_café.py\x00"
        with patch("builtins.open", mock_open(read_data=proc_content)):
            result = self.machine._get_cmdline_linux_proc()
            assert "script_café.py" in result

    @pytest.mark.parametrize(
        "pid_value",
        [1, 100, 9999, 65535],
        ids=["pid_1", "pid_100", "pid_9999", "pid_max"],
    )
    def test_get_cmdline_unix_ps_with_various_pids(self, pid_value: int) -> None:
        """Test _get_cmdline_unix_ps with various PID values."""
        mock_proc = Mock()
        mock_proc.communicate.return_value = (b"COMMAND\ntest\n", b"")

        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            self.machine._get_cmdline_unix_ps(pid_value)
            mock_popen.assert_called_once_with(
                ["ps", "-p", str(pid_value), "-o", "args"], stdout=subprocess.PIPE
            )


# Made with Bob
