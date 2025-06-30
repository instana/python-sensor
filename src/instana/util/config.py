# (c) Copyright IBM Corp. 2025

import itertools
import os
from typing import Any, Dict, List, Union

from instana.log import logger
from instana.util.config_reader import ConfigReader


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
