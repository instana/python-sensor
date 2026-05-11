# (c) Copyright IBM Corp. 2021, 2026
# (c) Copyright Instana Inc. 2021

"""
The Instana agent (for GCR) that manages
monitoring state and reporting that data.
"""

from instana.agent.serverless import ServerlessAgent
from instana.collector.google_cloud_run import GCRCollector
from instana.options import GCROptions


class GCRAgent(ServerlessAgent):
    """In-process agent for Google Cloud Run"""

    def __init__(self, service: str, configuration: str, revision: str) -> None:
        """
        Initialize with GCR-specific parameters.

        Args:
            service: GCR service name
            configuration: GCR configuration name
            revision: GCR revision name
        """
        self._service = service
        self._configuration = configuration
        self._revision = revision
        super().__init__()

    def _initialize_platform(self) -> None:
        """Initialize Google Cloud Run specific options."""
        self.options = GCROptions()

    def _create_collector(self) -> GCRCollector:
        """Create GCR collector with service parameters."""
        return GCRCollector(self, self._service, self._configuration, self._revision)

    def _get_entity_id(self) -> str:
        """Get GCR instance ID."""
        return self.collector.get_instance_id()

    def _get_cloud_provider(self) -> str:
        """Google Cloud Platform provider."""
        return "gcp"

    def _get_platform_name(self) -> str:
        """Platform name for logging."""
        return "Google Cloud Run"

    def _get_instana_host_header(self) -> str:
        """GCR uses custom formatted header."""
        return f"gcp:cloud-run:revision:{self.collector.revision}"


# Made with Bob
