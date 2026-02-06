# (c) Copyright IBM Corp. 2025

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


def parse_filtered_endpoints_string(params: Union[str, os.PathLike]) -> List[str]:
    """
    Parses a string to prepare a list of ignored endpoints.

    @param params: String format:
        - "service1:method1,method2;service2:method3" or "service1;service2"
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    span_filters = []
    if params:
        service_pairs = params.lower().split(";")

        for pair in service_pairs:
            if pair.strip():
                span_filters += parse_service_pair(pair)
    return span_filters


def parse_filtered_endpoints_dict(filter_dict: dict[str, Any]) -> dict[str, list[Any]]:
    """
    Parses 'exclude' and 'include' blocks from the filter dict.

    @param filter_dict: config_reader.data["com.instana.tracing"].get("filter")
    @return: Dict containing parsed rules for both exclude and include
    """
    parsed_config = {"exclude": [], "include": []}

    if not filter_dict or not isinstance(filter_dict, dict):
        return parsed_config

    # Disable filtering
    if filter_dict.get("deactivate", False):
        return parsed_config

    try:
        for mode in ["exclude", "include"]:
            raw_filters = filter_dict.get(mode, [])

            if not isinstance(raw_filters, list):
                continue

            for item in raw_filters:
                entry = {
                    "name": item.get("name", "unnamed"),
                    # Add suppression only for exclude mode
                    "suppression": item.get("suppression", True)
                    if mode == "exclude"
                    else None,
                    "attributes": [],
                }

                attributes = item.get("attributes", [])
                if isinstance(attributes, list):
                    for attr in attributes:
                        attr_data = {
                            "key": attr.get("key"),
                            "values": attr.get("values", []),
                            # match_type default: strict
                            "match_type": attr.get("match_type", "strict"),
                        }
                        entry["attributes"].append(attr_data)

                parsed_config[mode].append(entry)

        return parsed_config
    except Exception:
        return {"exclude": [], "include": []}


def parse_filtered_endpoints(
    params: Union[Dict[str, Any], str],
) -> Union[List[str], dict[str, list[Any]]]:
    """
    Parses input to prepare a list for ignored endpoints.

    @param params: Can be either:
        - String: "service1:method1,method2;service2:method3" or "service1;service2"
        - Dict: {"exclude": [{"name": "foo", "attributes": ...}], "include": []}
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*"]
    """
    try:
        if isinstance(params, str):
            return parse_filtered_endpoints_string(params)
        elif isinstance(params, dict):
            return parse_filtered_endpoints_dict(params)
        else:
            return []
    except Exception as e:
        logger.debug("Error parsing ignored endpoints: %s", str(e))
        return []


def parse_filtered_endpoints_from_yaml(
    file_path: str,
) -> Union[List[str], dict[str, list[Any]]]:
    """
    Parses configuration yaml file and prepares a list of ignored endpoints.

    @param file_path: Path of the file as a string
    @return: List of strings in format ["service1.method1", "service1.method2", "service2.*", "kafka.method.topic", "kafka.*.topic", "kafka.method.*"]
    """
    config_reader = ConfigReader(file_path)
    span_filters_dict = None
    if "tracing" in config_reader.data:
        span_filters_dict = config_reader.data["tracing"].get("filter")
    elif "com.instana.tracing" in config_reader.data:
        logger.warning(DEPRECATED_CONFIG_KEY_WARNING)
        span_filters_dict = config_reader.data["com.instana.tracing"].get("filter")
    if span_filters_dict:
        span_filters = parse_filtered_endpoints(span_filters_dict)
        return span_filters
    else:
        return []


def parse_span_filter_env_vars() -> Dict[str, List[Any]]:
    """
    Parses INSTANA_TRACING_FILTER_<POLICY>_<NAME>_ATTRIBUTES environment variables.

    @return: Dict containing parsed rules for both exclude and include
    """
    parsed_config = {"exclude": [], "include": []}

    # Intermediate storage: { "exclude": { "name": { "suppression": ..., "attributes": [] } } }
    intermediate = {"exclude": {}, "include": {}}

    for env_key, env_value in os.environ.items():
        if not env_key.startswith("INSTANA_TRACING_FILTER_"):
            continue

        parts = env_key.split("_")

        if len(parts) < 5:
            continue

        policy = parts[3].lower()
        if policy not in ["exclude", "include"]:
            continue

        suffix = parts[-1]
        name = "_".join(parts[4:-1])

        if not name:
            continue

        if name not in intermediate[policy]:
            intermediate[policy][name] = {
                "name": name,
                "attributes": [],
                "suppression": None,
            }

        if suffix == "ATTRIBUTES":
            # Rule format: key;values;match_type|key;values;match_type
            rules = env_value.split("|")
            for rule in rules:
                rule_parts = rule.split(";")
                if len(rule_parts) < 2:
                    continue

                key = rule_parts[0].strip()
                values_str = rule_parts[1]
                match_type = (
                    rule_parts[2].strip().lower() if len(rule_parts) > 2 else "strict"
                )

                # Split values by comma (simple split, assuming no commas in values or user handles escaping if needed?)
                # Spec says "values": Mandatory - List of Strings.
                # Env var examples: "http.target;/health" -> values=["/health"]
                # "kafka.service;topic1,topic2;strict" -> values=["topic1", "topic2"]
                values = [v.strip() for v in values_str.split(",") if v.strip()]

                attr_data = {"key": key, "values": values, "match_type": match_type}
                intermediate[policy][name]["attributes"].append(attr_data)

        elif suffix == "SUPPRESSION" and policy == "exclude":
            intermediate[policy][name]["suppression"] = is_truthy(env_value)

    # Convert intermediate to final list format
    for mode in ["exclude", "include"]:
        for name, data in intermediate[mode].items():
            # If suppression not set for exclude, default to True (as per YAML spec)
            if mode == "exclude" and data["suppression"] is None:
                data["suppression"] = True

            # Attributes are mandatory
            if data["attributes"]:
                parsed_config[mode].append(data)

    return parsed_config


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


# Made with Bob
