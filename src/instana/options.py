# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2016

"""
Option classes for the in-process Instana agent

The description and hierarchy of the classes in this file are as follows:

BaseOptions - base class for all environments.  Holds settings common to all.
  - StandardOptions - The options class used when running directly on a host/node with an Instana agent
  - ServerlessOptions - Base class for serverless environments.  Holds settings common to all serverless environments.
    - AWSLambdaOptions - Options class for AWS Lambda.  Holds settings specific to AWS Lambda.
    - AWSFargateOptions - Options class for AWS Fargate.  Holds settings specific to AWS Fargate.
    - GCROptions - Options class for Google cloud Run.  Holds settings specific to GCR.
"""

import logging
import os
from typing import Any, Dict, Sequence

from instana.configurator import config
from instana.log import logger
from instana.util.config import (
    SPAN_TYPE_TO_CATEGORY,
    get_disable_trace_configurations_from_env,
    get_disable_trace_configurations_from_local,
    get_disable_trace_configurations_from_yaml,
    is_truthy,
    parse_ignored_endpoints,
    parse_ignored_endpoints_from_yaml,
    parse_span_disabling,
)
from instana.util.runtime import determine_service_name


class BaseOptions(object):
    """Base class for all option classes.  Holds items common to all"""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        self.debug = False
        self.log_level = logging.WARN
        self.service_name = determine_service_name()
        self.extra_http_headers = None
        self.allow_exit_as_root = False
        self.ignore_endpoints = []
        self.kafka_trace_correlation = True

        # disabled_spans lists all categories and types that should be disabled
        self.disabled_spans = []
        # enabled_spans lists all categories and types that should be enabled, preceding disabled_spans
        self.enabled_spans = []

        self.set_trace_configurations()

        # Defaults
        self.secrets_matcher = "contains-ignore-case"
        self.secrets_list = ["key", "pass", "secret"]

        # Env var format: <matcher>:<secret>[,<secret>]
        self.secrets = os.environ.get("INSTANA_SECRETS", None)

        if self.secrets is not None:
            parts = self.secrets.split(":")
            if len(parts) == 2:
                self.secrets_matcher = parts[0]
                self.secrets_list = parts[1].split(",")
            else:
                logger.warning(
                    f"Couldn't parse INSTANA_SECRETS env var: {self.secrets}"
                )

        self.__dict__.update(kwds)

    def set_trace_configurations(self) -> None:
        """
        Set tracing configurations from the environment variables and config file.
        @return: None
        """
        # Use self.configurations to not read local configuration file
        # in set_tracing method
        if "INSTANA_DEBUG" in os.environ:
            self.log_level = logging.DEBUG
            self.debug = True

        if "INSTANA_EXTRA_HTTP_HEADERS" in os.environ:
            self.extra_http_headers = (
                str(os.environ["INSTANA_EXTRA_HTTP_HEADERS"]).lower().split(";")
            )

        # Check if either of the environment variables is truthy
        if is_truthy(os.environ.get("INSTANA_ALLOW_EXIT_AS_ROOT", None)) or is_truthy(
            os.environ.get("INSTANA_ALLOW_ROOT_EXIT_SPAN", None)
        ):
            self.allow_exit_as_root = True

        # The priority is as follows:
        # environment variables > in-code configuration >
        # > agent config (configuration.yaml) > default value
        if "INSTANA_IGNORE_ENDPOINTS" in os.environ:
            self.ignore_endpoints = parse_ignored_endpoints(
                os.environ["INSTANA_IGNORE_ENDPOINTS"]
            )
        elif "INSTANA_IGNORE_ENDPOINTS_PATH" in os.environ:
            self.ignore_endpoints = parse_ignored_endpoints_from_yaml(
                os.environ["INSTANA_IGNORE_ENDPOINTS_PATH"]
            )
        elif (
            isinstance(config.get("tracing"), dict)
            and "ignore_endpoints" in config["tracing"]
        ):
            self.ignore_endpoints = parse_ignored_endpoints(
                config["tracing"]["ignore_endpoints"],
            )

        if "INSTANA_KAFKA_TRACE_CORRELATION" in os.environ:
            self.kafka_trace_correlation = is_truthy(
                os.environ["INSTANA_KAFKA_TRACE_CORRELATION"]
            )
        elif isinstance(config.get("tracing"), dict) and "kafka" in config["tracing"]:
            self.kafka_trace_correlation = config["tracing"]["kafka"].get(
                "trace_correlation", True
            )

        self.set_disable_trace_configurations()

    def set_disable_trace_configurations(self) -> None:
        disabled_spans = []
        enabled_spans = []

        # The precedence is as follows:
        # environment variables > in-code (local) config > agent config (configuration.yaml)
        # For the env vars: INSTANA_TRACING_DISABLE > INSTANA_CONFIG_PATH
        if "INSTANA_TRACING_DISABLE" in os.environ:
            disabled_spans, enabled_spans = get_disable_trace_configurations_from_env()
        elif "INSTANA_CONFIG_PATH" in os.environ:
            disabled_spans, enabled_spans = get_disable_trace_configurations_from_yaml()
        else:
            # In-code (local) config
            # The agent config (configuration.yaml) is handled in StandardOptions.set_disable_tracing()
            disabled_spans, enabled_spans = (
                get_disable_trace_configurations_from_local()
            )

        self.disabled_spans.extend(disabled_spans)
        self.enabled_spans.extend(enabled_spans)

    def is_span_disabled(self, category=None, span_type=None) -> bool:
        """
        Check if a span is disabled based on its category and type.

        Args:
            category (str): The span category (e.g., "logging", "databases")
            span_type (str): The span type (e.g., "redis", "kafka")

        Returns:
            bool: True if the span is disabled, False otherwise
        """
        # If span_type is provided, check if it's disabled
        if span_type and span_type in self.disabled_spans:
            return True

        # If category is provided directly, check if it's disabled
        if category and category in self.disabled_spans:
            return True

        # If span_type is provided but not explicitly configured,
        # check if its parent category is disabled. Also check for the precedence rules
        if span_type and span_type in SPAN_TYPE_TO_CATEGORY:
            parent_category = SPAN_TYPE_TO_CATEGORY[span_type]
            if (
                parent_category in self.disabled_spans
                and span_type not in self.enabled_spans
            ):
                return True

        # Default: not disabled
        return False


class StandardOptions(BaseOptions):
    """The options class used when running directly on a host/node with an Instana agent"""

    AGENT_DEFAULT_HOST = "localhost"
    AGENT_DEFAULT_PORT = 42699

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(StandardOptions, self).__init__()

        self.agent_host = os.environ.get("INSTANA_AGENT_HOST", self.AGENT_DEFAULT_HOST)
        self.agent_port = os.environ.get("INSTANA_AGENT_PORT", self.AGENT_DEFAULT_PORT)

        if not isinstance(self.agent_port, int):
            self.agent_port = int(self.agent_port)

    def set_secrets(self, secrets: Dict[str, Any]) -> None:
        """
        Set the secret option from the agent config.
        @param secrets: dictionary of secrets
        @return: None
        """
        self.secrets_matcher = secrets["matcher"]
        self.secrets_list = secrets["list"]

    def set_extra_headers(self, extra_headers: Dict[str, Any]) -> None:
        """
        Set the extra headers option from the agent config, which uses the legacy configuration setting.
        @param extra_headers: dictionary of headers
        @return: None
        """
        if self.extra_http_headers is None:
            self.extra_http_headers = extra_headers
        else:
            self.extra_http_headers.extend(extra_headers)
        logger.info(
            f"Will also capture these custom headers: {self.extra_http_headers}"
        )

    def set_tracing(self, tracing: Dict[str, Any]) -> None:
        """
        Set tracing options from the agent config.
        @param tracing: tracing configuration dictionary
        @return: None
        """
        if "ignore-endpoints" in tracing and not self.ignore_endpoints:
            self.ignore_endpoints = parse_ignored_endpoints(tracing["ignore-endpoints"])

        if "kafka" in tracing:
            if (
                "INSTANA_KAFKA_TRACE_CORRELATION" not in os.environ
                and not (
                    isinstance(config.get("tracing"), dict)
                    and "kafka" in config["tracing"]
                )
                and "trace-correlation" in tracing["kafka"]
            ):
                self.kafka_trace_correlation = is_truthy(
                    tracing["kafka"].get("trace-correlation", True)
                )

            if (
                "header-format" in tracing["kafka"]
                and tracing["kafka"]["header-format"] == "binary"
            ):
                logger.warning(
                    "Binary header format for Kafka is deprecated. Please use string header format."
                )

        if "extra-http-headers" in tracing:
            self.extra_http_headers = tracing["extra-http-headers"]

        # Handle span disabling configuration
        if "disable" in tracing:
            self.set_disable_tracing(tracing["disable"])

    def set_disable_tracing(self, tracing_config: Sequence[Dict[str, Any]]) -> None:
        # The precedence is as follows:
        # environment variables > in-code (local) config > agent config (configuration.yaml)
        if (
            "INSTANA_TRACING_DISABLE" not in os.environ
            and "INSTANA_CONFIG_PATH" not in os.environ
            and not (
                isinstance(config.get("tracing"), dict)
                and "disable" in config["tracing"]
            )
        ):
            # agent config (configuration.yaml)
            disabled_spans, enabled_spans = parse_span_disabling(tracing_config)
            self.disabled_spans.extend(disabled_spans)
            self.enabled_spans.extend(enabled_spans)

    def set_from(self, res_data: Dict[str, Any]) -> None:
        """
        Set the source identifiers given to use by the Instana Host agent.
        @param res_data: source identifiers provided as announce response
        @return: None
        """
        if not res_data or not isinstance(res_data, dict):
            logger.debug(f"options.set_from: Wrong data type - {type(res_data)}")
            return

        if "secrets" in res_data:
            self.set_secrets(res_data["secrets"])

        if "tracing" in res_data:
            self.set_tracing(res_data["tracing"])

        else:
            if "extraHeaders" in res_data:
                self.set_extra_headers(res_data["extraHeaders"])


class ServerlessOptions(BaseOptions):
    """Base class for serverless environments.  Holds settings common to all serverless environments."""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(ServerlessOptions, self).__init__()

        self.agent_key = os.environ.get("INSTANA_AGENT_KEY", None)
        self.endpoint_url = os.environ.get("INSTANA_ENDPOINT_URL", None)

        # Remove any trailing slash (if any)
        if self.endpoint_url is not None and self.endpoint_url[-1] == "/":
            self.endpoint_url = self.endpoint_url[:-1]

        if "INSTANA_DISABLE_CA_CHECK" in os.environ:
            self.ssl_verify = False
        else:
            self.ssl_verify = True

        proxy = os.environ.get("INSTANA_ENDPOINT_PROXY", None)
        if proxy is None:
            self.endpoint_proxy = {}
        else:
            self.endpoint_proxy = {"https": proxy}

        timeout_in_ms = os.environ.get("INSTANA_TIMEOUT", None)
        if timeout_in_ms is None:
            self.timeout = 0.8
        else:
            # Convert the value from milliseconds to seconds for the requests package
            try:
                self.timeout = int(timeout_in_ms) / 1000
            except ValueError:
                logger.warning(
                    f"Likely invalid INSTANA_TIMEOUT={timeout_in_ms} value.  Using default."
                )
                logger.warning(
                    "INSTANA_TIMEOUT should specify timeout in milliseconds.  See "
                    "https://www.instana.com/docs/reference/environment_variables/#serverless-monitoring"
                )
                self.timeout = 0.8

        value = os.environ.get("INSTANA_LOG_LEVEL", None)
        if value is not None:
            try:
                value = value.lower()
                if value == "debug":
                    self.log_level = logging.DEBUG
                elif value == "info":
                    self.log_level = logging.INFO
                elif value == "warn" or value == "warning":
                    self.log_level = logging.WARNING
                elif value == "error":
                    self.log_level = logging.ERROR
                else:
                    logger.warning(f"Unknown INSTANA_LOG_LEVEL specified: {value}")
            except Exception:
                logger.debug("BaseAgent.update_log_level: ", exc_info=True)


class AWSLambdaOptions(ServerlessOptions):
    """Options class for AWS Lambda.  Holds settings specific to AWS Lambda."""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(AWSLambdaOptions, self).__init__()


class AWSFargateOptions(ServerlessOptions):
    """Options class for AWS Fargate.  Holds settings specific to AWS Fargate."""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(AWSFargateOptions, self).__init__()

        self.tags = None
        tag_list = os.environ.get("INSTANA_TAGS", None)
        if tag_list is not None:
            try:
                self.tags = dict()
                tags = tag_list.split(",")
                for tag_and_value in tags:
                    parts = tag_and_value.split("=")
                    length = len(parts)
                    if length == 1:
                        self.tags[parts[0]] = None
                    elif length == 2:
                        self.tags[parts[0]] = parts[1]
            except Exception:
                logger.debug(f"Error parsing INSTANA_TAGS env var: {tag_list}")

        self.zone = os.environ.get("INSTANA_ZONE", None)


class EKSFargateOptions(AWSFargateOptions):
    """Options class for EKS Pods on AWS Fargate. Holds settings specific to EKS Pods on AWS Fargate."""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(EKSFargateOptions, self).__init__()


class GCROptions(ServerlessOptions):
    """Options class for Google Cloud Run.  Holds settings specific to Google Cloud Run."""

    def __init__(self, **kwds: Dict[str, Any]) -> None:
        super(GCROptions, self).__init__()
