# (c) Copyright IBM Corp. 2025


from typing import Any, List


def matches_rule(rule_attributes: List[Any], span_attributes: List[Any]) -> bool:
    """Check if the span attributes match the rule attributes."""
    for attr_rule in rule_attributes:
        key = attr_rule.get("key")
        target_values = attr_rule.get("values", [])
        match_type = attr_rule.get("match_type", "strict")

        # Set the key to compare with the rules
        actual_value = span_attributes.get(key)
        if actual_value is None:
            return False

        actual_value = str(actual_value)

        # Check if the value is matching with the rule based on match_type
        val_match = False
        for val in target_values:
            val = str(val)
            if val == "*":  # Wildcard match
                val_match = True
            elif match_type == "strict" and actual_value == val:
                val_match = True
            elif match_type == "contains" and val in actual_value:
                val_match = True
            elif match_type == "startswith" and actual_value.startswith(val):
                val_match = True
            elif match_type == "endswith" and actual_value.endswith(val):
                val_match = True

            if val_match:
                break

        if not val_match:
            return False
    return True
