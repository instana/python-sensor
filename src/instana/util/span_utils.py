# (c) Copyright IBM Corp. 2025

from typing import Tuple


def get_operation_specifiers(span_name: str) -> Tuple[str, str]:
    """Get the specific operation specifier for the given span."""
    operation_specifier_key = ""
    service_specifier_key = ""
    if span_name == "redis":
        operation_specifier_key = "command"
    elif span_name == "dynamodb":
        operation_specifier_key = "op"
    elif span_name == "kafka":
        operation_specifier_key = "access"
        service_specifier_key = "service"
    return operation_specifier_key, service_specifier_key
