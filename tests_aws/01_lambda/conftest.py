# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import os
import sys

import pytest

os.environ["AWS_EXECUTION_ENV"] = "AWS_Lambda_python_3.10"

from instana.collector.base import BaseCollector

if sys.version_info <= (3, 8):
    print("Python runtime version not supported by AWS Lambda.")
    exit(1)


@pytest.fixture
def trace_id() -> int:
    return 1812338823475918251


@pytest.fixture
def span_id() -> int:
    return 6895521157646639861


def always_true(_: object) -> bool:
    return True


# Mocking BaseCollector.prepare_and_report_data()
@pytest.fixture(autouse=True)
def prepare_and_report_data(monkeypatch, request):
    """Return always True for BaseCollector.prepare_and_report_data()"""
    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original BaseCollector.prepare_and_report_data()
        monkeypatch.setattr(
            BaseCollector,
            "prepare_and_report_data",
            BaseCollector.prepare_and_report_data,
        )
    else:
        monkeypatch.setattr(BaseCollector, "prepare_and_report_data", always_true)
