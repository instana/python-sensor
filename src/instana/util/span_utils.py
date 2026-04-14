# (c) Copyright IBM Corp. 2025


from typing import Any, Optional

from instana.util.config import SPAN_TYPE_TO_CATEGORY


def matches_rule(rule_attributes: list[Any], span_attributes: list[Any]) -> bool:
    """Check if the span attributes match the rule attributes."""
    for attr_rule in rule_attributes:
        key = attr_rule.get("key")
        target_values = attr_rule.get("values", [])
        match_type = attr_rule.get("match_type", "strict")

        rule_matched = False

        if key == "category":
            if (
                "type" in span_attributes
                and span_attributes["type"] is not None
                and span_attributes["type"] in SPAN_TYPE_TO_CATEGORY
            ):
                actual = SPAN_TYPE_TO_CATEGORY[span_attributes["type"]]
                if actual in target_values:
                    rule_matched = True

        elif key == "kind":
            if "kind" in span_attributes:
                actual_kind = get_span_kind(span_attributes["kind"])
                if actual_kind in target_values:
                    rule_matched = True

        elif key == "type":
            if "type" in span_attributes and span_attributes["type"] in target_values:
                rule_matched = True

        else:
            span_value = None
            if key in span_attributes:
                span_value = span_attributes[key]
            elif "." in key:
                # Support dot-notation paths for nested attributes
                # e.g. "sdk.custom.tags.http.host" -> span["sdk.custom"]["tags"]["http.host"]
                span_value = resolve_nested_key(span_attributes, key.split("."))

            if span_value is not None:
                for rule_value in target_values:
                    if match_key_filter(span_value, rule_value, match_type):
                        rule_matched = True
                        break

        if not rule_matched:
            return False

    return True


def resolve_nested_key(data: dict[str, Any], key_parts: list[str]) -> Any:
    """Resolve a dotted key path against a potentially nested dict.

    Tries all possible prefix lengths so that keys which themselves contain
    dots (e.g. ``sdk.custom`` or ``http.host``) are handled correctly.

    Example::

        # span_attributes = {"sdk.custom": {"tags": {"http.host": "example.com"}}}
        resolve_nested_key(span_attributes, ["sdk", "custom", "tags", "http", "host"])
        # -> "example.com"
    """
    if not key_parts or not isinstance(data, dict):
        return None

    current_data = data
    remaining_parts = key_parts[:]

    while remaining_parts:
        found = False

        # Try the longest prefix first so that keys with embedded dots are matched
        # before shorter splits (e.g. prefer "sdk.custom" over "sdk").
        for i in range(len(remaining_parts), 0, -1):
            candidate = ".".join(remaining_parts[:i])

            if isinstance(current_data, dict) and candidate in current_data:
                if i == len(remaining_parts):
                    # We've consumed all remaining parts - return the value
                    return current_data[candidate]
                else:
                    # Move deeper into the structure
                    current_data = current_data[candidate]
                    remaining_parts = remaining_parts[i:]
                    found = True
                    break

        if not found:
            return None

    return None


def match_key_filter(span_value: str, rule_value: str, match_type: str) -> bool:
    """Check if the first value matches the second value based on the match type."""
    # Guard against None values
    if span_value is None:
        return False

    return bool(
        rule_value == "*"
        or (match_type == "strict" and span_value == rule_value)
        or (match_type == "contains" and rule_value in span_value)
        or (match_type == "startswith" and span_value.startswith(rule_value))
        or (match_type == "endswith" and span_value.endswith(rule_value))
    )


def get_span_kind(span_kind: Any) -> str:
    res = "intermediate"

    val = span_kind
    if hasattr(span_kind, "value"):
        val = span_kind.value

    try:
        k = int(val)
        if k == 1:
            res = "entry"
        elif k == 2:
            res = "exit"
    except (ValueError, TypeError):
        pass

    if res == "intermediate" and isinstance(span_kind, str):
        if span_kind.lower() in ["entry", "server"]:
            res = "entry"
        if span_kind.lower() in ["exit", "client"]:
            res = "exit"

    return res
