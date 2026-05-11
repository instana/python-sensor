# (c) Copyright IBM Corp. 2023, 2026

"""
The Instana agent (for AWS EKS Fargate) that manages
monitoring state and reporting that data.
"""

from instana.agent.serverless import ServerlessAgent
from instana.collector.aws_eks_fargate import EKSFargateCollector
from instana.collector.helpers.eks.process import get_pod_name
from instana.options import EKSFargateOptions


class EKSFargateAgent(ServerlessAgent):
    """In-process agent for AWS EKS Fargate"""

    def _initialize_platform(self) -> None:
        """Initialize EKS Fargate specific options and pod name."""
        self.options = EKSFargateOptions()
        self.podname = get_pod_name()

    def _create_collector(self) -> EKSFargateCollector:
        """Create EKS Fargate collector."""
        return EKSFargateCollector(self)

    def _get_entity_id(self) -> str:
        """Get Kubernetes pod name."""
        return self.podname

    def _get_cloud_provider(self) -> str:
        """Kubernetes cloud provider."""
        return "k8s"

    def _get_platform_name(self) -> str:
        """Platform name for logging."""
        return "EKS Pod on AWS Fargate"


# Made with Bob
