# (c) Copyright IBM Corp. 2025
# Assisted by watsonx Code Assistant

import logging
import os
import sys
from typing import TYPE_CHECKING, Generator, List, Union

import pytest

from instana.util.runtime import (
    determine_service_name,
    get_proc_cmdline,
    get_py_source,
    get_runtime_env_info,
    log_runtime_env_info,
)

if TYPE_CHECKING:
    from pytest import LogCaptureFixture
    from pytest_mock import MockerFixture


def test_get_py_source(tmp_path) -> None:
    """Test the get_py_source."""
    filename = "temp_file.py"
    file_contents = "print('Hello, World!')\n"
    expected_output = {"data": file_contents}

    # Create a temporary file for testing purposes.
    temp_file = tmp_path / filename
    temp_file.write_text(file_contents)

    result = get_py_source(f"{tmp_path}/{filename}")
    assert result == expected_output, f"Expected {expected_output}, but got {result}"


@pytest.mark.parametrize(
    "filename, expected_output",
    [
        (
            "non_existent_file.py",
            {"error": "[Errno 2] No such file or directory: 'non_existent_file.py'"}
        ),
        ("temp_file.txt", {"error": "Only Python source files are allowed. (*.py)"}),
    ],
)
def test_get_py_source_error(filename, expected_output) -> None:
    """Test the get_py_source function with various scenarios with errors."""
    result = get_py_source(filename)
    assert result == expected_output, f"Expected {expected_output}, but got {result}"


def test_get_py_source_exception(mocker) -> None:
    """Test the get_py_source function with an exception scenario."""
    exception_message = "No such file or directory"
    mocker.patch(
        "instana.util.runtime.get_py_source", side_effect=Exception(exception_message)
    )

    with pytest.raises(Exception) as exc_info:
        get_py_source("/path/to/non_readable_file.py")
        assert str(exc_info.value) == exception_message, (
            f"Expected {exception_message}, but got {exc_info.value}"
        )


@pytest.fixture()
def _resource_determine_service_name_via_env_var() -> Generator[None, None, None]:
    """SetUp and TearDown"""
    # setup
    yield
    # teardown
    os.environ.pop("INSTANA_SERVICE_NAME", None)
    os.environ.pop("FLASK_APP", None)
    os.environ.pop("DJANGO_SETTINGS_MODULE", None)


@pytest.mark.parametrize(
    "env_var, value, expected_output",
    [
        ("INSTANA_SERVICE_NAME", "test_service", "test_service"),
        ("FLASK_APP", "test_flask_app.py", "test_flask_app.py"),
        ("DJANGO_SETTINGS_MODULE", "test_django_app.settings", "test_django_app"),
    ],
)
def test_determine_service_name_via_env_var(
    env_var: str,
    value: str,
    expected_output: str,
    _resource_determine_service_name_via_env_var: None,
) -> None:
    # Test with multiple environment variables
    os.environ[env_var] = value
    sys.argv = ["something", "nothing"]
    assert determine_service_name() == expected_output


@pytest.mark.parametrize(
    "web_browser, argv, expected_output",
    [
        ("gunicorn", ["gunicorn", "djface.wsgi:app"], "gunicorn"),
        (
            "uwsgi",
            [
                "uwsgi",
                "--master",
                "--processes",
                "4",
                "--threads",
                "2",
                "djface.wsgi:app",
            ],
            "uWSGI master",
        ),
    ],
)
def test_determine_service_name_via_web_browser(
    web_browser: str,
    argv: List[str],
    expected_output: str,
    _resource_determine_service_name_via_env_var: None,
    mocker: "MockerFixture",
) -> None:
    mocker.patch("instana.util.runtime.get_proc_cmdline", return_value="python")
    mocker.patch("os.getpid", return_value=12345)
    sys.argv = argv
    assert determine_service_name() == expected_output


@pytest.mark.parametrize(
    "argv",
    [
        (["python", "test_app.py", "arg1", "arg2"]),
        ([]),
    ],
)
def test_determine_service_name_via_cli_args(
    argv: List[str],
    _resource_determine_service_name_via_env_var: None,
    mocker: "MockerFixture",
) -> None:
    mocker.patch("instana.util.runtime.get_proc_cmdline", return_value="python")
    sys.argv = argv
    # We check "python" in the return of determine_service_name() because this 
    # can be the value "python3"
    assert "python" in determine_service_name()


@pytest.mark.parametrize(
    "isatty, expected_output",
    [
        (True, "Interactive Console"),
        (False, ""),
    ],
)
def test_determine_service_name_via_tty(
    isatty: bool,
    expected_output: str,
    _resource_determine_service_name_via_env_var: None,
    mocker: "MockerFixture",
) -> None:
    sys.argv = []
    sys.executable = ""
    sys.stdout.isatty = lambda: isatty
    assert determine_service_name() == expected_output


@pytest.mark.parametrize(
    "as_string, expected",
    [
        (False, ["python", "script.py", "arg1", "arg2"]),
        (True, "python script.py arg1 arg2"),
    ],
)
def test_get_proc_cmdline(as_string: bool, expected: Union[List[str], str], mocker: "MockerFixture") -> None:
    # Mock the proc filesystem presence
    mocker.patch("os.path.isfile", return_value="/proc/self/cmdline")
    # Mock the content of /proc/self/cmdline
    mocked_data = mocker.mock_open(read_data="python\0script.py\0arg1\0arg2\0")
    mocker.patch("builtins.open", mocked_data)

    assert get_proc_cmdline(as_string) == expected, f"Expected {expected}, but got {get_proc_cmdline(as_string)}"


@pytest.mark.parametrize(
    "as_string, expected",
    [
        (False, ["python"]),
        (True, "python"),
    ],
)
def test_get_proc_cmdline_no_proc_fs(
    as_string: bool, expected: Union[List[str], str], mocker: "MockerFixture"
):
    # Mock the proc filesystem absence
    mocker.patch("os.path.isfile", return_value=False)
    assert get_proc_cmdline(as_string) == expected



def test_get_runtime_env_info(mocker: "MockerFixture") -> None:
    """Test the get_runtime_env_info function."""
    expected_output = ("x86_64", "3.13.5")

    mocker.patch("platform.machine", return_value=expected_output[0])
    mocker.patch("platform.python_version", return_value=expected_output[1])

    machine, py_version = get_runtime_env_info()
    assert machine == expected_output[0]
    assert py_version == expected_output[1]


def test_log_runtime_env_info(mocker: "MockerFixture", caplog: "LogCaptureFixture") -> None:
    """Test the log_runtime_env_info function."""
    expected_output = ("x86_64", "3.13.5")
    caplog.set_level(logging.DEBUG, logger="instana")

    mocker.patch("platform.machine", return_value=expected_output[0])
    mocker.patch("platform.python_version", return_value=expected_output[1])

    log_runtime_env_info()
    assert (
        f"Runtime environment: Machine: {expected_output[0]}, Python version: {expected_output[1]}"
        in caplog.messages
    )
