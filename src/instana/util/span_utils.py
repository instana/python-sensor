# (c) Copyright IBM Corp. 2025

from typing import Optional


def get_operation_specifier(span_name: str) -> Optional[str]:
    """Get the specific operation specifier for the given span."""
    operation_specifier = ""
    if span_name == "redis":
        operation_specifier = "command"
    elif span_name == "dynamodb":
        operation_specifier = "op"
    return operation_specifier
