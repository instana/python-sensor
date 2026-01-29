# (c) Copyright IBM Corp. 2025

from typing import Any, Dict, Tuple

from opentelemetry.trace import SpanKind

from instana.span.kind import HTTP_SPANS
from instana.util.config import SPAN_TYPE_TO_CATEGORY


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


def extract_span_attributes(span: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract filterable attributes from span for filtering logic.

    Args:
        span: Span dictionary with 'n' (name), 'k' (kind), 'data' fields

    Returns:
        Dictionary with:
            - category: str (from SPAN_TYPE_TO_CATEGORY mapping)
            - kind: str (entry/exit/intermediate)
            - type: str (span.n or span.name)
            - span_attrs: dict (span.data[type] attributes if available)
    """
    result = {
        "category": None,
        "kind": None,
        "type": None,
        "span_attrs": {},
    }

    # Extract span type (n or name)
    span_type = getattr(span, "n", None) or getattr(span, "name", None)
    if span_type:
        result["type"] = span_type
        # Map type to category
        result["category"] = SPAN_TYPE_TO_CATEGORY.get(span_type)

    # Extract span kind
    span_kind = getattr(span, "k", None)
    if span_kind is not None:
        if span_kind == SpanKind.SERVER:
            result["kind"] = "entry"
        elif span_kind == SpanKind.CLIENT:
            result["kind"] = "exit"
        elif span_kind == SpanKind.INTERNAL:
            result["kind"] = "intermediate"

    # Extract span-specific attributes from data
    span_data = getattr(span, "data", None) or (
        span.get("data") if isinstance(span, dict) else None
    )

    result["span_attrs"] = {}

    if span_data and isinstance(span_data, dict):
        # For HTTP spans, data is stored under "http" key
        if span_type in HTTP_SPANS and "http" in span_data:
            http_data = span_data.get("http", {})
            # Check if http_data has actual values (not just None values)
            if http_data and any(v is not None for v in dict(http_data).values()):
                result["span_attrs"] = http_data
        elif span_type and span_type in span_data:
            type_data = span_data.get(span_type, {})
            # Check if type_data has actual values (not just None values)
            if type_data and any(v is not None for v in dict(type_data).values()):
                result["span_attrs"] = type_data

        # Fallback: Check sdk.custom.tags for test spans created with set_attribute()
        if not result["span_attrs"]:
            sdk_data = span_data.get("sdk", {})
            if sdk_data and isinstance(sdk_data, dict):
                custom = sdk_data.get("custom", {})
                if custom and isinstance(custom, dict):
                    tags = custom.get("tags", {})
                    if tags and isinstance(tags, dict):
                        # Extract attributes matching span_type prefix (e.g., "redis.command")
                        prefix = f"{span_type}."
                        for key, value in tags.items():
                            if key.startswith(prefix):
                                # Remove prefix to get attribute name (e.g., "command")
                                attr_name = key[len(prefix) :]
                                result["span_attrs"][attr_name] = value

    return result


def matches_filter_value(
    actual: str,
    expected: str,
    match_type: str = "strict",
) -> bool:
    """
    Check if actual value matches expected based on match_type.

    Args:
        actual: The actual value from span
        expected: The expected value from filter rule
        match_type: One of: strict, startswith, endswith, contains

    Returns:
        True if matches, False otherwise
    """
    if not isinstance(actual, str) or not isinstance(expected, str):
        return False

    actual = actual.lower()
    expected = expected.lower()

    if match_type == "startswith":
        return actual.startswith(expected)
    elif match_type == "endswith":
        return actual.endswith(expected)
    elif match_type == "contains":
        return expected in actual
    else:  # strict (default)
        return actual == expected


def matches_filter_rule(
    span_attrs: Dict[str, Any],
    rule: Dict[str, Any],
) -> bool:
    """
    Check if span attributes match a filter rule.

    Uses AND logic: all attributes in the rule must match.

    Args:
        span_attrs: Extracted span attributes (category, kind, type, span_attrs)
        rule: Filter rule with 'attributes' list

    Returns:
        True if all attributes match, False otherwise
    """
    if "attributes" not in rule:
        return False

    # All attributes must match (AND logic)
    for attr_filter in rule["attributes"]:
        if not matches_attribute_filter(span_attrs, attr_filter):
            return False

    return True


def matches_attribute_filter(
    span_attrs: Dict[str, Any],
    attr_filter: Dict[str, Any],
) -> bool:
    """
    Check if a single attribute filter matches the span.

    Args:
        span_attrs: Extracted span attributes
        attr_filter: Single attribute filter with 'key', 'values', 'match_type'

    Returns:
        True if any value matches (OR logic for values), False otherwise
    """
    key = attr_filter.get("key", "")
    values = attr_filter.get("values", [])
    match_type = attr_filter.get("match_type", "strict")

    if not key or not values:
        return False

    # Get the actual value from span based on key
    actual_value = None

    if key == "category":
        actual_value = span_attrs.get("category")
    elif key == "kind":
        actual_value = span_attrs.get("kind")
    elif key == "type":
        actual_value = span_attrs.get("type")
    else:
        # Span-specific attribute (e.g., http.url, kafka.service)
        span_data = span_attrs.get("span_attrs", {})
        # Extract the attribute name after the dot (e.g., "url" from "http.url")
        if "." in key:
            attr_name = key.split(".", 1)[1]
            actual_value = span_data.get(attr_name)

    if actual_value is None:
        return False

    # Check if any value matches (OR logic for values)
    for expected_value in values:
        if matches_filter_value(str(actual_value), str(expected_value), match_type):
            return True

    return False
