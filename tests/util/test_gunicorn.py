# (c) Copyright IBM Corp. 2026

import os
import sys
from unittest import mock

import pytest

from instana.log import running_in_gunicorn


class TestRunningInGunicorn:
    """Test suite for running_in_gunicorn() function"""

    @pytest.mark.parametrize(
        "argv,expected,description",
        [
            # Positive cases - gunicorn should be detected
            (["gunicorn", "app:application"], True, "gunicorn as first argument"),
            (["python", "-m", "gunicorn", "app"], True, "gunicorn in middle"),
            (["/usr/bin/gunicorn", "--workers=4"], True, "gunicorn with full path"),
            (["/path/to/gunicorn.py"], True, "gunicorn in filename"),
            (["gunicorn"], True, "gunicorn alone"),
            (
                ["python", "gunicorn_wrapper.py", "--config=gunicorn.conf"],
                True,
                "multiple gunicorn occurrences",
            ),
            (
                ["/home/user/.local/bin/gunicorn", "myapp:app"],
                True,
                "gunicorn in user bin",
            ),
            # Negative cases - gunicorn should NOT be detected
            (["python", "manage.py", "runserver"], False, "django runserver"),
            (["uwsgi", "--http", ":8000"], False, "uwsgi server"),
            (["unicorn", "app"], False, "similar name unicorn"),
            (["python", "gun.py"], False, "partial match gun"),
            ([], False, "empty argv"),
            (["python", "app.py"], False, "regular python script"),
            (["flask", "run"], False, "flask development server"),
            (["GUNICORN", "app"], False, "uppercase GUNICORN"),
        ],
    )
    def test_detection_via_sys_argv(self, monkeypatch, argv, expected, description):
        """Test gunicorn detection via sys.argv"""
        monkeypatch.setattr(sys, "argv", argv)
        result = running_in_gunicorn()
        assert result == expected, f"Failed: {description}"

    @pytest.mark.parametrize(
        "cmdline_content,expected,description",
        [
            # Positive cases - gunicorn in cmdline
            (
                "gunicorn\0app:application\0",
                True,
                "gunicorn as first command",
            ),
            (
                "/usr/bin/gunicorn\0--workers=4\0",
                True,
                "gunicorn with full path",
            ),
            (
                "python\0-m\0gunicorn\0app\0",
                True,
                "gunicorn via python -m",
            ),
            (
                "/home/user/.local/bin/gunicorn\0myapp:app\0",
                True,
                "gunicorn in user directory",
            ),
            (
                "gunicorn\0",
                True,
                "gunicorn alone with null byte",
            ),
            # Negative cases - no gunicorn in cmdline
            (
                "python\0manage.py\0runserver\0",
                False,
                "django runserver",
            ),
            (
                "uwsgi\0--http\0:8000\0",
                False,
                "uwsgi server",
            ),
            (
                "unicorn\0app\0",
                False,
                "similar name unicorn",
            ),
            (
                "",
                False,
                "empty cmdline",
            ),
            (
                "python\0app.py\0",
                False,
                "regular python script",
            ),
        ],
    )
    def test_detection_via_proc_cmdline(
        self, monkeypatch, cmdline_content, expected, description
    ):
        """Test gunicorn detection via /proc/self/cmdline when sys.argv is not available"""
        # Remove sys.argv to force fallback to /proc/self/cmdline
        monkeypatch.delattr(sys, "argv", raising=False)

        # Mock os.path.isfile to return True for /proc/self/cmdline
        monkeypatch.setattr(os.path, "isfile", lambda x: x == "/proc/self/cmdline")

        # Mock file open to return cmdline content
        mock_open = mock.mock_open(read_data=cmdline_content)
        monkeypatch.setattr("builtins.open", mock_open)

        result = running_in_gunicorn()
        assert result == expected, f"Failed: {description}"

        # Verify file was opened if sys.argv was not available
        if not hasattr(sys, "argv"):
            mock_open.assert_called_once_with("/proc/self/cmdline")

    def test_fallback_to_proc_cmdline_when_no_sys_argv(self, monkeypatch):
        """Test that function falls back to /proc/self/cmdline when sys.argv is not available"""
        # Remove sys.argv attribute
        monkeypatch.delattr(sys, "argv", raising=False)

        # Mock /proc/self/cmdline with gunicorn
        monkeypatch.setattr(os.path, "isfile", lambda x: x == "/proc/self/cmdline")
        mock_open = mock.mock_open(read_data="gunicorn\0app:application\0")
        monkeypatch.setattr("builtins.open", mock_open)

        result = running_in_gunicorn()

        assert result is True
        mock_open.assert_called_once_with("/proc/self/cmdline")

    def test_proc_cmdline_not_exists(self, monkeypatch):
        """Test when /proc/self/cmdline does not exist"""
        # Remove sys.argv to force fallback
        monkeypatch.delattr(sys, "argv", raising=False)

        # Mock os.path.isfile to return False
        monkeypatch.setattr(os.path, "isfile", lambda x: False)

        result = running_in_gunicorn()
        assert result is False

    def test_sys_argv_with_none_values(self, monkeypatch):
        """Test handling of None values in sys.argv"""
        # This should not crash, but may not find gunicorn
        monkeypatch.setattr(sys, "argv", ["python", None, "app.py"])

        # Should handle gracefully and return False (or raise exception which is caught)
        result = running_in_gunicorn()
        assert result is False

    def test_sys_argv_with_non_string_values(self, monkeypatch):
        """Test handling of non-string values in sys.argv"""
        monkeypatch.setattr(sys, "argv", ["python", 123, "app.py"])

        # Should handle gracefully
        result = running_in_gunicorn()
        assert result is False

    def test_empty_sys_argv(self, monkeypatch):
        """Test with empty sys.argv list"""
        monkeypatch.setattr(sys, "argv", [])

        result = running_in_gunicorn()
        assert result is False

    @pytest.mark.parametrize(
        "cmdline_content,expected,description",
        [
            ("", False, "empty content"),
            ("\0", False, "single null byte"),
            ("python\0\0\0app.py\0", False, "multiple consecutive null bytes"),
            (
                "python\0" + "\0".join(["arg"] * 1000) + "\0gunicorn\0app\0",
                True,
                "very long command line with gunicorn",
            ),
            (
                "python\0" + "\0".join(["arg"] * 1000) + "\0app\0",
                False,
                "very long command line without gunicorn",
            ),
            ("   \0   \0", False, "whitespace with null bytes"),
            ("\0\0\0", False, "only null bytes"),
        ],
    )
    def test_proc_cmdline_edge_cases(
        self, monkeypatch, cmdline_content, expected, description
    ):
        """Test /proc/self/cmdline with various edge case contents"""
        monkeypatch.delattr(sys, "argv", raising=False)
        monkeypatch.setattr(os.path, "isfile", lambda x: x == "/proc/self/cmdline")

        mock_open = mock.mock_open(read_data=cmdline_content)
        monkeypatch.setattr("builtins.open", mock_open)

        result = running_in_gunicorn()
        assert result == expected, f"Failed: {description}"

    def test_case_sensitivity(self, monkeypatch):
        """Test that detection is case-sensitive"""
        # Test uppercase - should not match
        monkeypatch.setattr(sys, "argv", ["GUNICORN", "app"])
        result = running_in_gunicorn()
        assert result is False

        # Test mixed case - should not match
        monkeypatch.setattr(sys, "argv", ["Gunicorn", "app"])
        result = running_in_gunicorn()
        assert result is False

        # Test lowercase - should match
        monkeypatch.setattr(sys, "argv", ["gunicorn", "app"])
        result = running_in_gunicorn()
        assert result is True

    def test_partial_match_in_argv(self, monkeypatch):
        """Test that partial matches work correctly"""
        # These should match (gunicorn is substring)
        test_cases_match = [
            ["/usr/local/bin/gunicorn"],
            ["python", "/path/to/gunicorn.py"],
            ["gunicorn_wrapper"],
        ]

        for argv in test_cases_match:
            monkeypatch.setattr(sys, "argv", argv)
            result = running_in_gunicorn()
            assert result is True, f"Should match for argv: {argv}"

        # These should NOT match (gunicorn is not substring)
        test_cases_no_match = [
            ["unicorn"],
            ["gun"],
            ["gunicor"],
        ]

        for argv in test_cases_no_match:
            monkeypatch.setattr(sys, "argv", argv)
            result = running_in_gunicorn()
            assert result is False, f"Should not match for argv: {argv}"

    def test_real_world_gunicorn_command_lines(self, monkeypatch):
        """Test with realistic gunicorn command line examples"""
        real_world_cases = [
            # Standard gunicorn invocation
            ["gunicorn", "myapp:app", "--bind", "0.0.0.0:8000"],
            # With workers
            ["gunicorn", "myapp:app", "-w", "4", "-b", "127.0.0.1:8000"],
            # With config file
            ["gunicorn", "-c", "gunicorn_config.py", "myapp:app"],
            # Via python module
            ["python", "-m", "gunicorn", "myapp:app"],
            # With full path
            ["/usr/local/bin/gunicorn", "myapp:app", "--daemon"],
            # In virtual environment
            ["/home/user/venv/bin/gunicorn", "myapp:app"],
        ]

        for argv in real_world_cases:
            monkeypatch.setattr(sys, "argv", argv)
            result = running_in_gunicorn()
            assert result is True, f"Should detect gunicorn in: {argv}"

    def test_no_side_effects(self, monkeypatch):
        """Test that function doesn't modify global state"""
        original_argv = ["gunicorn", "app"]
        monkeypatch.setattr(sys, "argv", original_argv.copy())

        running_in_gunicorn()

        # sys.argv should remain unchanged
        assert sys.argv == original_argv

    def test_idempotency(self, monkeypatch):
        """Test that multiple calls return the same result"""
        monkeypatch.setattr(sys, "argv", ["gunicorn", "app"])

        result1 = running_in_gunicorn()
        result2 = running_in_gunicorn()
        result3 = running_in_gunicorn()

        assert result1 == result2 == result3 is True

        monkeypatch.setattr(sys, "argv", ["python", "app.py"])

        result4 = running_in_gunicorn()
        result5 = running_in_gunicorn()

        assert result4 == result5 is False


# Made with Bob
