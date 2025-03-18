from typing import Optional
import pytest

from instana.util.span_utils import get_operation_specifier


@pytest.mark.parametrize(
    "span_name, expected_result",
    [("something", ""), ("redis", "command"), ("dynamodb", "op")],
)
def test_get_operation_specifier(
    span_name: str, expected_result: Optional[str]
) -> None:
    response_redis = get_operation_specifier(span_name)
    assert response_redis == expected_result
