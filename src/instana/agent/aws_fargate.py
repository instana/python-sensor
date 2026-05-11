# (c) Copyright IBM Corp. 2021, 2026
# (c) Copyright Instana Inc. 2020

"""
The Instana agent (for AWS Fargate) that manages
monitoring state and reporting that data.
"""

from instana.agent.serverless import ServerlessAgent
from instana.collector.aws_fargate import AWSFargateCollector
from instana.options import AWSFargateOptions


class AWSFargateAgent(ServerlessAgent):
    """In-process agent for AWS Fargate"""

    def _initialize_platform(self) -> None:
        """Initialize AWS Fargate specific options."""
        self.options = AWSFargateOptions()

    def _create_collector(self) -> AWSFargateCollector:
        """Create AWS Fargate collector."""
        return AWSFargateCollector(self)

    def _get_entity_id(self) -> str:
        """Get Fargate task ARN."""
        return self.collector.get_fq_arn()

    def _get_cloud_provider(self) -> str:
        """AWS cloud provider."""
        return "aws"

    def _get_platform_name(self) -> str:
        """Platform name for logging."""
        return "AWS Fargate"


# Made with Bob
