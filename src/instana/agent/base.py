# (c) Copyright IBM Corp. 2021, 2026
# (c) Copyright Instana Inc. 2020

"""
Base class for all the agent flavors
"""

import logging
from typing import TYPE_CHECKING, Any

import requests

from instana.log import logger
from instana.util.span_utils import matches_rule

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


class BaseAgent(object):
    """Base class for all agent flavors"""

    client = None
    options = None

    def __init__(self) -> None:
        self.client = requests.Session()

    def update_log_level(self) -> None:
        """Uses the value in <self.log_level> to update the global logger"""
        if self.options is None or self.options.log_level not in [
            logging.DEBUG,
            logging.INFO,
            logging.WARN,
            logging.ERROR,
        ]:
            logger.warning("BaseAgent.update_log_level: Unknown log level set")
            return

        logger.setLevel(self.options.log_level)

    def filter_spans(self, spans: list["InstanaSpan"]) -> list["InstanaSpan"]:
        """
        Filters span list using hierarchical filtering rules.

        Args:
            spans: List of Spans

        Returns:
            List of Spans that pass the filtering rules
        """
        filtered_spans = []

        for span in spans:
            if self._is_span_missing_required_attributes(span):
                filtered_spans.append(span)
                continue

            service_name = ""

            # Set the service name
            for span_value in span.data:
                if isinstance(span.data[span_value], dict):
                    service_name = span_value

            # Skip if no valid service name found
            if not service_name:
                filtered_spans.append(span)
                continue

            # Set span attributes for filtering
            attributes_to_check = {
                "type": service_name,
                "kind": getattr(span, "k", None),
            }

            # Add operation specifiers to the attributes
            for key, value in span.data[service_name].items():
                attributes_to_check[f"{service_name}.{key}"] = value

            # Check if the span need to be ignored
            if self._is_endpoint_ignored(attributes_to_check):
                continue

            filtered_spans.append(span)

        return filtered_spans

    def _is_endpoint_ignored(self, span_attributes: dict[str, Any]) -> bool:
        """
        Check if a span should be ignored based on filtering rules.

        Include rules have precedence over exclude rules:
        - If an include rule matches, the span is NOT ignored (returns False)
        - If no include rules exist or none match, check exclude rules
        - If an exclude rule matches, the span IS ignored (returns True)
        - If no rules match, the span is NOT ignored (returns False)

        Args:
            span_attributes: Dictionary of span attributes to check

        Returns:
            True if span should be filtered out, False otherwise
        """
        if not span_attributes or not isinstance(span_attributes, dict):
            return False

        filters = self.options.span_filters
        if not filters:
            return False

        # Include rules have highest precedence - if matched, span is kept
        include_rules = filters.get("include", [])
        if self._matches_rules(include_rules, span_attributes):
            return False

        # Check exclude rules only if no include rule matched
        exclude_rules = filters.get("exclude", [])
        return bool(self._matches_rules(exclude_rules, span_attributes))

    def _matches_rules(self, rules: list[dict], span_attributes: dict) -> bool:
        """
        Check if span matches any provided rule.

        Args:
            rules: List of Dictionary containing filter rules
            span_attributes: Dictionary of span attributes to check

        Returns:
            True if any rule matches, False otherwise
        """
        return any(
            matches_rule(rule.get("attributes", []), span_attributes) for rule in rules
        )

    def _is_span_missing_required_attributes(self, span: "InstanaSpan") -> bool:
        """
        Checks if a span is missing required attributes for filtering.

        Args:
            span: InstanaSpan

        Returns:
            True if span is missing required attributes, False otherwise
        """
        has_name_attribute = hasattr(span, "n") or hasattr(span, "name")
        has_data_attribute = hasattr(span, "data")
        return not has_name_attribute or not has_data_attribute
