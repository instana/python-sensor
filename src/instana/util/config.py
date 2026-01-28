# (c) Copyright IBM Corp. 2025

import itertools
import os
from typing import Any, Dict, List, Sequence, Tuple, Union, Optional

from instana.configurator import config
from instana.log import logger
from instana.util.config_reader import ConfigReader

# Constants
DEPRECATED_CONFIG_KEY_WARNING = 'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'

# List of supported span categories (technology or protocol)
SPAN_CATEGORIES = [
    "logging",
    "databases",
    "messaging",
    "protocols",  # http, grpc, etc.
]

# Mapping of span type calls (framework, library name, instrumentation name) to categories
SPAN_TYPE_TO_CATEGORY = {
    # Database types
    "redis": "databases",
    "mysql": "databases",
    "postgresql": "databases",
    "mongodb": "databases",
    "cassandra": "databases",
    "couchbase": "databases",
    "dynamodb": "databases",
    "sqlalchemy": "databases",
    # Messaging types
    "kafka": "messaging",
    "rabbitmq": "messaging",
    "pika": "messaging",
    "aio_pika": "messaging",
    "aioamqp": "messaging",
    # Protocol types
    "http": "protocols",
    "grpc": "protocols",
    "graphql": "protocols",
}


def parse_service_pair(pair: str) -> List[str]:
    """
    Parses a pair string to prepare a list of ignored endpoints.

    @param pair: String format:
        - "service1:method1,method2" or "service1:method1" or "service1"
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    pair_list = []
    if ":" in pair:
        service, methods = pair.split(":", 1)
        service = service.strip()
        method_list = [ep.strip() for ep in methods.split(",") if ep.strip()]

        for method in method_list:
            pair_list.append(f"{service}.{method}")
    else:
        pair_list.append(f"{pair}.*")
    return pair_list


def parse_ignored_endpoints_string(params: Union[str, os.PathLike]) -> List[str]:
    """
    Parses a string to prepare a list of ignored endpoints.

    @param params: String format:
        - "service1:method1,method2;service2:method3" or "service1;service2"
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    ignore_endpoints = []
    if params:
        service_pairs = params.lower().split(";")

        for pair in service_pairs:
            if pair.strip():
                ignore_endpoints += parse_service_pair(pair)
    return ignore_endpoints


def parse_ignored_endpoints_dict(params: Dict[str, Any]) -> List[str]:
    """
    Parses a dictionary to prepare a list of ignored endpoints.

    @param params: Dict format:
        - {"service1": ["method1", "method2"], "service2": ["method3"]}
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    ignore_endpoints = []

    for service, methods in params.items():
        if not methods:  # filtering all service
            ignore_endpoints.append(f"{service.lower()}.*")
        else:  # filtering specific endpoints
            ignore_endpoints = parse_endpoints_of_service(
                ignore_endpoints, service, methods
            )

    return ignore_endpoints


def parse_endpoints_of_service(
    ignore_endpoints: List[str],
    service: str,
    methods: Union[str, List[str]],
) -> List[str]:
    """
    Parses endpoints of each service.

    @param ignore_endpoints: A list of rules for endpoints to be filtered.
    @param service: The name of the service to be filtered.
    @param methods: A list of specific endpoints of the service to be filtered.
    """
    if service == "kafka" and isinstance(methods, list):
        for rule in methods:
            ignore_endpoints.extend(parse_kafka_methods(rule))
    else:
        for method in methods:
            ignore_endpoints.append(f"{service.lower()}.{method.lower()}")
    return ignore_endpoints


def parse_kafka_methods(rule: Union[str, Dict[str, any]]) -> List[str]:
    parsed_rule = []
    if isinstance(rule, dict):
        for method, endpoint in itertools.product(rule["methods"], rule["endpoints"]):
            parsed_rule.append(f"kafka.{method.lower()}.{endpoint.lower()}")
    elif isinstance(rule, list):
        for method in rule:
            parsed_rule.append(f"kafka.{method.lower()}.*")
    else:
        parsed_rule.append(f"kafka.{rule.lower()}.*")
    return parsed_rule


def parse_ignored_endpoints(params: Union[Dict[str, Any], str]) -> List[str]:
    """
    Parses input to prepare a list for ignored endpoints.

    @param params: Can be either:
        - String: "service1:method1,method2;service2:method3" or "service1;service2"
        - Dict: {"service1": ["method1", "method2"], "service2": ["method3"]}
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    try:
        if isinstance(params, str):
            return parse_ignored_endpoints_string(params)
        elif isinstance(params, dict):
            return parse_ignored_endpoints_dict(params)
        else:
            return []
    except Exception as e:
        logger.debug("Error parsing ignored endpoints: %s", str(e))
        return []


def parse_ignored_endpoints_from_yaml(file_path: str) -> List[str]:
    """
    Parses configuration yaml file and prepares a list of ignored endpoints.

    @param file_path: Path of the file as a string
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*", "kafka.method.topic", "kafka.*.topic", "kafka.method.*"]
    """
    config_reader = ConfigReader(file_path)
    ignore_endpoints_dict = None
    if "tracing" in config_reader.data:
        ignore_endpoints_dict = config_reader.data["tracing"].get("ignore-endpoints")
    elif "com.instana.tracing" in config_reader.data:
        logger.warning(DEPRECATED_CONFIG_KEY_WARNING)
        ignore_endpoints_dict = config_reader.data["com.instana.tracing"].get(
            "ignore-endpoints"
        )
    if ignore_endpoints_dict:
        ignored_endpoints = parse_ignored_endpoints(ignore_endpoints_dict)
        return ignored_endpoints
    else:
        return []


def is_truthy(value: Any) -> bool:
    """
    Check if a value is truthy, accepting various formats.

    @param value: The value to check
    @return: True if the value is considered truthy, False otherwise

    Accepts the following as True:
    - True (Python boolean)
    - "True", "true" (case-insensitive string)
    - "1" (string)
    - 1 (integer)
    """
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value == 1

    if isinstance(value, str):
        value_lower = value.lower()
        return value_lower == "true" or value == "1"

    return False


def parse_span_disabling(
    disable_list: Sequence[Union[str, Dict[str, Any]]],
) -> Tuple[List[str], List[str]]:
    """
    Process a list of span disabling configurations and return lists of disabled and enabled spans.

    @param disable_list: List of span disabling configurations
    @return: Tuple of (disabled_spans, enabled_spans)
    """
    if not isinstance(disable_list, list):
        logger.debug(
            f"parse_span_disabling: Invalid disable_list type: {type(disable_list)}"
        )
        return [], []

    disabled_spans = []
    enabled_spans = []

    for item in disable_list:
        if isinstance(item, str):
            disabled = parse_span_disabling_str(item)
            disabled_spans.extend(disabled)
        elif isinstance(item, dict):
            disabled, enabled = parse_span_disabling_dict(item)
            disabled_spans.extend(disabled)
            enabled_spans.extend(enabled)
        else:
            logger.debug(
                f"parse_span_disabling: Invalid disable_list item type: {type(item)}"
            )

    return disabled_spans, enabled_spans


def parse_span_disabling_str(item: str) -> List[str]:
    """
    Process a string span disabling configuration and return a list of disabled spans.

    @param item: String span disabling configuration
    @return: List of disabled spans
    """
    if item.lower() in SPAN_CATEGORIES or item.lower() in SPAN_TYPE_TO_CATEGORY.keys():
        return [item.lower()]
    else:
        logger.debug(f"set_span_disabling_str: Invalid span category/type: {item}")
        return []


def parse_span_disabling_dict(items: Dict[str, bool]) -> Tuple[List[str], List[str]]:
    """
    Process a dictionary span disabling configuration and return lists of disabled and enabled spans.

    @param items: Dictionary span disabling configuration
    @return: Tuple of (disabled_spans, enabled_spans)
    """
    disabled_spans = []
    enabled_spans = []

    for key, value in items.items():
        if key in SPAN_CATEGORIES or key in SPAN_TYPE_TO_CATEGORY.keys():
            if is_truthy(value):
                disabled_spans.append(key)
            else:
                enabled_spans.append(key)
        else:
            logger.debug(f"set_span_disabling_dict: Invalid span category/type: {key}")

    return disabled_spans, enabled_spans


def get_disable_trace_configurations_from_env() -> Tuple[List[str], List[str]]:
    # Read INSTANA_TRACING_DISABLE environment variable
    if tracing_disable := os.environ.get("INSTANA_TRACING_DISABLE", None):
        if is_truthy(tracing_disable):
            # INSTANA_TRACING_DISABLE is True/true/1, then we disable all tracing
            disabled_spans = []
            for category in SPAN_CATEGORIES:
                disabled_spans.append(category)
            return disabled_spans, []
        else:
            # INSTANA_TRACING_DISABLE is a comma-separated list of span categories/types
            tracing_disable_list = [x.strip() for x in tracing_disable.split(",")]
            return parse_span_disabling(tracing_disable_list)
    return [], []


def get_tracing_root_key(config_data: Dict[str, Any]) -> Optional[str]:
    """
    Get the root key for tracing configuration from config data.
    Handles both 'tracing' and deprecated 'com.instana.tracing' keys.

    Args:
        config_data: Configuration data dictionary

    Returns:
        Root key string or None if not found
    """
    if "tracing" in config_data:
        return "tracing"
    elif "com.instana.tracing" in config_data:
        logger.warning(DEPRECATED_CONFIG_KEY_WARNING)
        return "com.instana.tracing"
    return None


def get_disable_trace_configurations_from_yaml() -> Tuple[List[str], List[str]]:
    config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))

    root_key = get_tracing_root_key(config_reader.data)
    if not root_key:
        return [], []

    if tracing_disable_config := config_reader.data[root_key].get("disable", None):
        return parse_span_disabling(tracing_disable_config)
    return [], []


def get_disable_trace_configurations_from_local() -> Tuple[List[str], List[str]]:
    if "tracing" in config:
        if tracing_disable_config := config["tracing"].get("disable", None):
            return parse_span_disabling(tracing_disable_config)
    return [], []


def validate_stack_trace_level(level_value: Any, context: str = "") -> Optional[str]:
    """
    Validate stack trace level value.

    Args:
        level_value: The level value to validate
        context: Context string for error messages (e.g., "for kafka", "in agent config")

    Returns:
        Validated level string ("all", "error", or "none"), or None if invalid
    """
    level = str(level_value).lower()
    if level in ["all", "error", "none"]:
        return level

    context_msg = f" {context}" if context else ""
    logger.warning(
        f"Invalid stack-trace value{context_msg}: {level}. Must be 'all', 'error', or 'none'. Using default 'all'."
    )
    return None


def validate_stack_trace_length(length_value: Any, context: str = "") -> Optional[int]:
    """
    Validate stack trace length value.

    Args:
        length_value: The length value to validate
        context: Context string for error messages (e.g., "for kafka", "in agent config")

    Returns:
        Validated length integer (>= 1), or None if invalid
    """
    try:
        length = int(length_value)
        if length >= 1:
            return length

        context_msg = f" {context}" if context else ""
        logger.warning(
            f"stack-trace-length{context_msg} must be positive. Using default 30."
        )
        return None
    except (ValueError, TypeError):
        context_msg = f" {context}" if context else ""
        logger.warning(
            f"Invalid stack-trace-length{context_msg}. Must be an integer. Using default 30."
        )
        return None


def parse_technology_stack_trace_config(
    tech_data: Dict[str, Any],
    level_key: str = "stack-trace",
    length_key: str = "stack-trace-length",
    tech_name: str = "",
) -> Dict[str, Union[str, int]]:
    """
    Parse technology-specific stack trace configuration from a dictionary.

    Args:
        tech_data: Dictionary containing stack trace configuration
        level_key: Key name for level configuration (e.g., "stack-trace" or "stack_trace")
        length_key: Key name for length configuration (e.g., "stack-trace-length" or "stack_trace_length")
        tech_name: Technology name for error messages (e.g., "kafka", "redis")

    Returns:
        Dictionary with "level" and/or "length" keys, or empty dict if no valid config
    """
    tech_stack_config = {}
    context = f"for {tech_name}" if tech_name else ""

    if level_key in tech_data:
        if validated_level := validate_stack_trace_level(tech_data[level_key], context):
            tech_stack_config["level"] = validated_level

    if length_key in tech_data:
        if validated_length := validate_stack_trace_length(
            tech_data[length_key], context
        ):
            tech_stack_config["length"] = validated_length

    return tech_stack_config


def parse_global_stack_trace_config(global_config: Dict[str, Any]) -> Tuple[str, int]:
    """
    Parse global stack trace configuration from a config dictionary.

    Args:
        global_config: Global configuration dictionary

    Returns:
        Tuple of (level, length) with defaults if not found
    """
    level = "all"
    length = 30

    if "stack-trace" in global_config:
        if validated_level := validate_stack_trace_level(
            global_config["stack-trace"], "in YAML config"
        ):
            level = validated_level

    if "stack-trace-length" in global_config:
        if validated_length := validate_stack_trace_length(
            global_config["stack-trace-length"], "in YAML config"
        ):
            length = validated_length

    return level, length


def parse_tech_specific_stack_trace_configs(
    tracing_data: Dict[str, Any],
) -> Dict[str, Dict[str, Union[str, int]]]:
    """
    Parse technology-specific stack trace configurations from tracing data.

    Args:
        tracing_data: Tracing configuration dictionary

    Returns:
        Dictionary of technology-specific overrides
    """
    tech_config = {}

    for tech_name, tech_data in tracing_data.items():
        if tech_name == "global" or not isinstance(tech_data, dict):
            continue

        tech_stack_config = parse_technology_stack_trace_config(
            tech_data,
            level_key="stack-trace",
            length_key="stack-trace-length",
            tech_name=tech_name,
        )

        if tech_stack_config:
            tech_config[tech_name] = tech_stack_config

    return tech_config


def get_stack_trace_config_from_yaml() -> (
    Tuple[str, int, Dict[str, Dict[str, Union[str, int]]]]
):
    """
    Get stack trace configuration from YAML file specified by INSTANA_CONFIG_PATH.

    Returns:
        Tuple of (level, length, tech_config) where:
        - level: "all", "error", or "none"
        - length: positive integer
        - tech_config: Dict of technology-specific overrides
          Format: {"kafka": {"level": "all", "length": 35}, "redis": {"level": "none"}}
    """
    config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))

    level = "all"
    length = 30
    tech_config = {}

    root_key = get_tracing_root_key(config_reader.data)
    if not root_key:
        return level, length, tech_config

    tracing_data = config_reader.data[root_key]

    # Read global configuration
    if "global" in tracing_data:
        level, length = parse_global_stack_trace_config(tracing_data["global"])

    # Read technology-specific overrides
    tech_config = parse_tech_specific_stack_trace_configs(tracing_data)

    return level, length, tech_config


def parse_span_filter_rules(rule_string: str) -> List[Dict[str, Any]]:
    """
    Parses a string of span filter rules.
    Format: <key>;<values>;<match_type>|<key>;<values>;<match_type>
    """
    rules = []
    if not rule_string:
        return rules

    supported_match_types = {"strict", "startswith", "endswith", "contains"}
    raw_rules = rule_string.split("|")
    for raw_rule in raw_rules:
        parts = raw_rule.split(";")
        if len(parts) >= 2:
            key = parts[0].strip()
            # values are comma separated
            values = [v.strip() for v in parts[1].split(",") if v.strip()]
            match_type = parts[2].strip().lower() if len(parts) > 2 else "strict"

            # Validate match_type
            if match_type not in supported_match_types:
                logger.warning(
                    f"Unsupported match_type '{match_type}' for span filter rule with key '{key}'. "
                    f"Supported values are: {', '.join(sorted(supported_match_types))}. Defaulting to 'strict'."
                )
                match_type = "strict"

            if key and values:
                rules.append({"key": key, "values": values, "match_type": match_type})
    return rules


def parse_span_filter_config(filter_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses the span filter configuration dictionary according to the filter specification.

    Validates and normalizes filter rules:
    - Sets default values for optional fields
    - Validates suppression is only used with exclude policy
    - Ensures match_type defaults to 'strict'
    """
    parsed_config: Dict[str, Any] = {"deactivate": False, "include": [], "exclude": []}

    if not filter_config:
        return parsed_config

    if "deactivate" in filter_config:
        parsed_config["deactivate"] = is_truthy(filter_config["deactivate"])

    # Parse exclude rules
    if "exclude" in filter_config and isinstance(filter_config["exclude"], list):
        for rule in filter_config["exclude"]:
            if not isinstance(rule, dict):
                continue

            normalized_rule = _normalize_filter_rule(rule, policy="exclude")
            if normalized_rule:
                parsed_config["exclude"].append(normalized_rule)

    # Parse include rules
    if "include" in filter_config and isinstance(filter_config["include"], list):
        for rule in filter_config["include"]:
            if not isinstance(rule, dict):
                continue

            normalized_rule = _normalize_filter_rule(rule, policy="include")
            if normalized_rule:
                parsed_config["include"].append(normalized_rule)

    return parsed_config


def _normalize_filter_rule(
    rule: Dict[str, Any], policy: str
) -> Optional[Dict[str, Any]]:
    """
    Normalize a single filter rule according to specification.

    Args:
        rule: Raw filter rule from configuration
        policy: Either 'exclude' or 'include'

    Returns:
        Normalized rule dict or None if invalid
    """
    if "name" not in rule or "attributes" not in rule:
        logger.debug(
            "Skipping filter rule: missing required 'name' or 'attributes' field"
        )
        return None

    normalized = {"name": rule["name"], "attributes": []}

    # Handle suppression field (only valid for exclude policy, default: True)
    if "suppression" in rule:
        if policy == "exclude":
            normalized["suppression"] = is_truthy(rule["suppression"])
        else:
            logger.warning(
                f"Filter rule '{rule['name']}': 'suppression' is only valid for 'exclude' policy, ignoring"
            )
    elif policy == "exclude":
        # Default suppression to True for exclude rules
        normalized["suppression"] = True

    # Normalize attributes
    if not isinstance(rule["attributes"], list):
        logger.debug(
            f"Skipping filter rule '{rule['name']}': 'attributes' must be a list"
        )
        return None

    for attr in rule["attributes"]:
        if not isinstance(attr, dict) or "key" not in attr or "values" not in attr:
            logger.debug(
                f"Skipping invalid attribute in rule '{rule['name']}': missing 'key' or 'values'"
            )
            continue

        normalized_attr = {
            "key": attr["key"],
            "values": attr["values"]
            if isinstance(attr["values"], list)
            else [attr["values"]],
        }

        # Only include match_type if explicitly provided
        if "match_type" in attr:
            match_type = attr["match_type"]
            # Validate match_type
            valid_match_types = {"strict", "startswith", "endswith", "contains"}
            if match_type not in valid_match_types:
                logger.warning(
                    f"Invalid match_type '{match_type}' in rule '{rule['name']}'. "
                    f"Defaulting to 'strict'. Valid types: {', '.join(sorted(valid_match_types))}"
                )
                match_type = "strict"
            normalized_attr["match_type"] = match_type

        normalized["attributes"].append(normalized_attr)

    # Rule must have at least one valid attribute
    if not normalized["attributes"]:
        logger.debug(f"Skipping filter rule '{rule['name']}': no valid attributes")
        return None

    return normalized


def get_span_filter_config_from_yaml() -> Dict[str, Any]:
    """
    Get span filter configuration from YAML file specified by INSTANA_CONFIG_PATH.
    """
    config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))

    root_key = get_tracing_root_key(config_reader.data)
    if not root_key or root_key not in config_reader.data:
        return {}

    tracing_config = config_reader.data[root_key]
    if "filter" in tracing_config:
        return parse_span_filter_config(tracing_config["filter"])

    return {}


# Made with Bob
