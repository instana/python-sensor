# (c) Copyright IBM Corp. 2025

from typing import List, Optional
import pytest

from instana.util.span_utils import get_operation_specifiers


@pytest.mark.parametrize(
    "span_name, expected_result",
    [
        ("something", ["", ""]),
        ("redis", ["command", ""]),
        ("dynamodb", ["op", ""]),
        ("kafka", ["access", "service"]),
    ],
)
def test_get_operation_specifiers(
    span_name: str,
    expected_result: Optional[List[str]],
) -> None:
    operation_specifier, service_specifier = get_operation_specifiers(span_name)
    assert operation_specifier == expected_result[0]
    assert service_specifier == expected_result[1]
