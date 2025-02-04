from typing import Any, Dict, List, Union
from instana.log import logger


def parse_service_pair(pair: str) -> List[str]:
    """
    Parses a pair string to prepare a list of ignored endpoints.

    @param pair: String format:
        - "service1:endpoint1,endpoint2" or "service1:endpoint1" or "service1"
    @return: List of strings in format ["service1.endpoint1", "service1.endpoint2", "service2"]
    """
    pair_list = []
    if ":" in pair:
        service, endpoints = pair.split(":", 1)
        service = service.strip()
        endpoint_list = [ep.strip() for ep in endpoints.split(",") if ep.strip()]

        for endpoint in endpoint_list:
            pair_list.append(f"{service}.{endpoint}")
    else:
        pair_list.append(pair)
    return pair_list


def parse_ignored_endpoints_string(params: str) -> List[str]:
    """
    Parses a string to prepare a list of ignored endpoints.

    @param params: String format:
        - "service1:endpoint1,endpoint2;service2:endpoint3" or "service1;service2"
    @return: List of strings in format ["service1.endpoint1", "service1.endpoint2", "service2"]
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
        - {"service1": ["endpoint1", "endpoint2"], "service2": ["endpoint3"]}
    @return: List of strings in format ["service1.endpoint1", "service1.endpoint2", "service2"]
    """
    ignore_endpoints = []

    for service, endpoints in params.items():
        if not endpoints:  # filtering all service
            ignore_endpoints.append(service.lower())
        else:  # filtering specific endpoints
            for endpoint in endpoints:
                ignore_endpoints.append(f"{service.lower()}.{endpoint.lower()}")

    return ignore_endpoints


def parse_ignored_endpoints(params: Union[Dict[str, Any], str]) -> List[str]:
    """
    Parses input to prepare a list for ignored endpoints.

    @param params: Can be either:
        - String: "service1:endpoint1,endpoint2;service2:endpoint3" or "service1;service2"
        - Dict: {"service1": ["endpoint1", "endpoint2"], "service2": ["endpoint3"]}
    @return: List of strings in format ["service1.endpoint1", "service1.endpoint2", "service2"]
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
