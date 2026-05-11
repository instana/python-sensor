# (c) Copyright IBM Corp. 2026

"""
Base class for all serverless agent implementations.
Provides common functionality while allowing platform-specific customization.
"""

from abc import abstractmethod
from typing import Any, Optional

from requests import Response

from instana.agent.base import BaseAgent
from instana.log import logger
from instana.util import to_json
from instana.util.runtime import log_runtime_env_info
from instana.version import VERSION


class ServerlessAgent(BaseAgent):
    """
    Abstract base class for serverless agents.

    Implements common serverless functionality following the Template Method pattern.
    Subclasses must implement platform-specific abstract methods.

    This class eliminates code duplication across serverless platforms by providing
    a single implementation of common logic while allowing platform-specific
    customization through abstract methods.
    """

    # Constants
    CONTENT_TYPE = "application/json"
    BUNDLE_ENDPOINT = "/bundle"

    def __init__(self) -> None:
        """
        Initialize serverless agent with common setup.

        This template method orchestrates the initialization process:
        1. Call parent __init__
        2. Platform-specific initialization
        3. Common initialization (logging, validation)
        4. Collector creation and startup
        """
        super().__init__()

        self.collector = None
        self.report_headers = None
        self._can_send = False

        # Platform-specific initialization (implemented by subclasses)
        self._initialize_platform()

        # Common initialization
        self.update_log_level()
        self._log_startup()
        log_runtime_env_info()

        # Validate and start
        if self._validate_options():
            self._can_send = True
            self.collector = self._create_collector()
            self.collector.start()
        else:
            self._log_validation_failure()

    # Template Methods (implemented here, used by all subclasses)

    def can_send(self) -> bool:
        """
        Check if agent can send data.

        Returns:
            True if agent is ready to send data, False otherwise
        """
        return self._can_send

    def get_from_structure(self) -> dict[str, Any]:
        """
        Build the 'from' structure for monitoring data.

        This structure identifies the source of the monitoring data.

        Returns:
            Dictionary with 'hl' (headerless), 'cp' (cloud provider), and 'e' (entity)
        """
        return {
            "hl": True,
            "cp": self._get_cloud_provider(),
            "e": self._get_entity_id(),
        }

    def report_data_payload(self, payload: dict[str, Any]) -> Optional[Response]:
        """
        Report metrics and span data to the endpoint.

        Template method that orchestrates the reporting process:
        1. Prepare payload (filter spans)
        2. Prepare headers (lazy initialization)
        3. Send HTTP request
        4. Validate response

        Args:
            payload: Dictionary containing metrics and spans

        Returns:
            HTTP Response object or None if error occurred
        """
        response = None
        try:
            # Step 1: Prepare payload (filter spans)
            payload = self._prepare_payload(payload)

            # Step 2: Prepare headers (lazy initialization)
            if self.report_headers is None:
                self.report_headers = self._build_headers()

            # Step 3: Send request
            response = self._send_http_request(payload)

            # Step 4: Validate response
            self._validate_response(response)

        except Exception as exc:
            logger.debug("report_data_payload: connection error (%s)", type(exc))

        return response

    def _validate_options(self) -> bool:
        """
        Validate that required options are set.

        Returns:
            True if options are valid, False otherwise
        """
        return (
            self.options.endpoint_url is not None and self.options.agent_key is not None
        )

    # Protected Helper Methods (used internally by template methods)

    def _prepare_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Filter spans and prepare payload for transmission.

        Extracts spans from payload, filters them using inherited filter_spans(),
        and updates the payload with filtered spans.

        Args:
            payload: Original payload dictionary

        Returns:
            Modified payload with filtered spans
        """
        spans = payload.get("spans", [])
        filtered_spans = self.filter_spans(spans)

        if len(filtered_spans) > 0:
            logger.debug(f"Reporting {len(filtered_spans)} spans")
            payload["spans"] = filtered_spans

        return payload

    def _build_headers(self) -> dict[str, str]:
        """
        Build HTTP headers for requests.

        Creates standard headers required by Instana backend and allows
        platform-specific headers through _get_custom_headers().

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": self.CONTENT_TYPE,
            "X-Instana-Host": self._get_instana_host_header(),
            "X-Instana-Key": self.options.agent_key,
        }

        # Allow platform-specific headers
        custom_headers = self._get_custom_headers()
        if custom_headers:
            headers.update(custom_headers)

        return headers

    def _send_http_request(self, payload: dict[str, Any]) -> Response:
        """
        Execute HTTP POST request to backend.

        Args:
            payload: Data to send

        Returns:
            HTTP Response object
        """
        return self.client.post(
            self._get_endpoint_url(),
            data=to_json(payload),
            headers=self.report_headers,
            timeout=self.options.timeout,
            verify=self.options.ssl_verify,
            proxies=self.options.endpoint_proxy,
        )

    def _validate_response(self, response: Response) -> None:
        """
        Validate HTTP response and log if needed.

        Args:
            response: HTTP Response object to validate
        """
        if not 200 <= response.status_code < 300:
            logger.info(
                f"report_data_payload: Instana responded with "
                f"status code {response.status_code}"
            )

    def _get_endpoint_url(self) -> str:
        """
        Get the full endpoint URL for data submission.

        Returns:
            Complete URL string
        """
        return f"{self.options.endpoint_url}{self.BUNDLE_ENDPOINT}"

    def _log_startup(self) -> None:
        """Log agent startup message."""
        logger.info(
            f"Stan is on the {self._get_platform_name()} scene. "
            f"Starting Instana instrumentation version: {VERSION}"
        )

    def _log_validation_failure(self) -> None:
        """Log validation failure message."""
        logger.warning(
            "Required INSTANA_AGENT_KEY and/or INSTANA_ENDPOINT_URL "
            f"environment variables not set. We will not be able to "
            f"monitor this {self._get_platform_name()}."
        )

    # Abstract Methods (must be implemented by subclasses)

    @abstractmethod
    def _initialize_platform(self) -> None:
        """
        Perform platform-specific initialization.

        This is called early in __init__ before common initialization.
        Use this to set up platform-specific attributes (e.g., options, podname).

        Example:
            def _initialize_platform(self):
                self.options = AWSFargateOptions()
        """
        pass

    @abstractmethod
    def _create_collector(self):
        """
        Create and return the platform-specific collector instance.

        Returns:
            Collector instance for this platform

        Example:
            def _create_collector(self):
                return AWSFargateCollector(self)
        """
        pass

    @abstractmethod
    def _get_entity_id(self) -> str:
        """
        Get the platform-specific entity identifier.

        Examples:
        - AWS Fargate: Fully qualified ARN
        - AWS Lambda: Fully qualified ARN
        - EKS Fargate: Pod name
        - GCR: Instance ID

        Returns:
            Entity identifier string

        Example:
            def _get_entity_id(self):
                return self.collector.get_fq_arn()
        """
        pass

    @abstractmethod
    def _get_cloud_provider(self) -> str:
        """
        Get the cloud provider code.

        Returns:
            Cloud provider code: 'aws', 'gcp', or 'k8s'

        Example:
            def _get_cloud_provider(self):
                return "aws"
        """
        pass

    @abstractmethod
    def _get_platform_name(self) -> str:
        """
        Get the human-readable platform name for logging.

        Returns:
            Platform name (e.g., 'AWS Fargate', 'Google Cloud Run')

        Example:
            def _get_platform_name(self):
                return "AWS Fargate"
        """
        pass

    def _get_instana_host_header(self) -> str:
        """
        Get the value for the X-Instana-Host header.

        Default implementation returns entity ID.
        Override for custom header values (e.g., GCR's formatted string).

        Returns:
            Header value string
        """
        return self._get_entity_id()

    def _get_custom_headers(self) -> Optional[dict[str, str]]:
        """
        Get platform-specific custom headers.

        Override to add additional headers beyond the standard ones.

        Returns:
            Dictionary of custom headers or None
        """
        return None


# Made with Bob
