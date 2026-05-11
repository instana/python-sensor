# (c) Copyright IBM Corp. 2021, 2026
# (c) Copyright Instana Inc. 2020

"""
The Instana Agent for AWS Lambda functions that manages
monitoring state and reporting that data.
"""

from instana.agent.serverless import ServerlessAgent
from instana.collector.aws_lambda import AWSLambdaCollector
from instana.options import AWSLambdaOptions


class AWSLambdaAgent(ServerlessAgent):
    """In-process Agent for AWS Lambda"""

    def _initialize_platform(self) -> None:
        """Initialize AWS Lambda specific options."""
        self.options = AWSLambdaOptions()

    def _create_collector(self) -> AWSLambdaCollector:
        """Create AWS Lambda collector."""
        return AWSLambdaCollector(self)

    def _get_entity_id(self) -> str:
        """Get Lambda function ARN."""
        return self.collector.get_fq_arn()

    def _get_cloud_provider(self) -> str:
        """AWS cloud provider."""
        return "aws"

    def _get_platform_name(self) -> str:
        """Platform name for logging."""
        return "AWS Lambda"


# Made with Bob
