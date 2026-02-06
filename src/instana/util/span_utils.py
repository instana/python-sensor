# (c) Copyright IBM Corp. 2025


from typing import Any, List

from instana.util.config import SPAN_TYPE_TO_CATEGORY


def matches_rule(rule_attributes: List[Any], span_attributes: List[Any]) -> bool:
    """Check if the span attributes match the rule attributes."""
    for attr_rule in rule_attributes:
        key = attr_rule.get("key")
        target_values = attr_rule.get("values", [])
        match_type = attr_rule.get("match_type", "strict")

        rule_matched = False

        if key == "category":
            if (
                "type" in span_attributes
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
            if "type" in span_attributes:
                if span_attributes["type"] in target_values:
                    rule_matched = True

        else:
            if key in span_attributes:
                span_value = span_attributes[key]
                for rule_value in target_values:
                    if match_key_filter(span_value, rule_value, match_type):
                        rule_matched = True
                        break

        if not rule_matched:
            return False

    return True


def match_key_filter(span_value: str, rule_value: str, match_type: str) -> bool:
    """Check if the first value matches the second value based on the match type."""
    if rule_value == "*":
        return True
    elif match_type == "strict" and span_value == rule_value:
        return True
    elif match_type == "contains" and rule_value in span_value:
        return True
    elif match_type == "startswith" and span_value.startswith(rule_value):
        return True
    elif match_type == "endswith" and span_value.endswith(rule_value):
        return True

    return False


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
