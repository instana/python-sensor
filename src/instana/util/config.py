# (c) Copyright IBM Corp. 2025

import itertools
import os
from typing import Any, Dict, List, Sequence, Tuple, Union

from instana.configurator import config
from instana.log import logger
from instana.util.config_reader import ConfigReader

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
        logger.warning(
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
        )
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


def get_disable_trace_configurations_from_yaml() -> Tuple[List[str], List[str]]:
    config_reader = ConfigReader(os.environ.get("INSTANA_CONFIG_PATH", ""))

    if "tracing" in config_reader.data:
        root_key = "tracing"
    elif "com.instana.tracing" in config_reader.data:
        logger.warning(
            'Please use "tracing" instead of "com.instana.tracing" for local configuration file.'
        )
        root_key = "com.instana.tracing"
    else:
        return [], []

    tracing_disable_config = config_reader.data[root_key].get("disable", "")
    return parse_span_disabling(tracing_disable_config)


def get_disable_trace_configurations_from_local() -> Tuple[List[str], List[str]]:
    if "tracing" in config:
        if tracing_disable_config := config["tracing"].get("disable", None):
            return parse_span_disabling(tracing_disable_config)
    return [], []


# Made with Bob
