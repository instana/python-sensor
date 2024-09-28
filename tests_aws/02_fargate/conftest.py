import os
import pytest

os.environ["AWS_EXECUTION_ENV"] = "AWS_ECS_FARGATE"

from instana.collector.aws_fargate import AWSFargateCollector

# Mocking AWSFargateCollector.get_ecs_metadata()
@pytest.fixture(autouse=True)
def get_ecs_metadata(monkeypatch, request) -> None:
    """Return always True for AWSFargateCollector.get_ecs_metadata()"""

    def _always_true(_: object) -> bool:
        return True

    if "original" in request.keywords:
        # If using the `@pytest.mark.original` marker before the test function,
        # uses the original AWSFargateCollector.get_ecs_metadata()
        monkeypatch.setattr(AWSFargateCollector, "get_ecs_metadata", AWSFargateCollector.get_ecs_metadata)
    else:
        monkeypatch.setattr(AWSFargateCollector, "get_ecs_metadata", _always_true)
