# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import logging
import os
from typing import Generator
from unittest.mock import patch

import pytest
import redis

from instana.options import StandardOptions
from instana.singletons import agent, tracer
from instana.span.span import get_current_span
from tests.helpers import testenv


class TestRedis:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.recorder = tracer.span_processor
        self.recorder.clear_spans()
        self.client = redis.Redis(host=testenv["redis_host"], db=testenv["redis_db"])
        yield
        if "INSTANA_IGNORE_ENDPOINTS" in os.environ.keys():
            del os.environ["INSTANA_IGNORE_ENDPOINTS"]
        agent.options.allow_exit_as_root = False

    def test_set_get(self) -> None:
        result = None
        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.set("fooy", "barY")
            result = self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        assert result == b"barX"

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert rs1_span.t == test_span.t
        assert rs2_span.t == test_span.t
        assert rs3_span.t == test_span.t

        # Parent relationships
        assert rs1_span.p == test_span.s
        assert rs2_span.p == test_span.s
        assert rs3_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not rs1_span.ec
        assert not rs2_span.ec
        assert not rs3_span.ec

        # Redis span 1
        assert rs1_span.n == "redis"
        assert "custom" not in rs1_span.data
        assert "redis" in rs1_span.data

        assert rs1_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs1_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs1_span.data["redis"]["command"] == "SET"
        assert not rs1_span.data["redis"]["error"]

        assert rs1_span.stack
        assert isinstance(rs1_span.stack, list)
        assert len(rs1_span.stack) > 0

        # Redis span 2
        assert rs2_span.n == "redis"
        assert "custom" not in rs2_span.data
        assert "redis" in rs2_span.data

        assert rs2_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs2_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs2_span.data["redis"]["command"] == "SET"
        assert not rs2_span.data["redis"]["error"]

        assert rs2_span.stack
        assert isinstance(rs2_span.stack, list)
        assert len(rs2_span.stack) > 0

        # Redis span 3
        assert rs3_span.n == "redis"
        assert "custom" not in rs3_span.data
        assert "redis" in rs3_span.data

        assert rs3_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs3_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs3_span.data["redis"]["command"] == "GET"
        assert not rs3_span.data["redis"]["error"]

        assert rs3_span.stack
        assert isinstance(rs3_span.stack, list)
        assert len(rs3_span.stack) > 0

    def test_set_get_as_root_span(self) -> None:
        agent.options.allow_exit_as_root = True

        self.client.set("foox", "barX")
        self.client.set("fooy", "barY")
        result = self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        assert result == b"barX"

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Parent relationships
        assert not rs1_span.p
        assert not rs2_span.p
        assert not rs3_span.p

        # Error logging
        assert not rs1_span.ec
        assert not rs2_span.ec
        assert not rs3_span.ec

        # Redis span 1
        assert rs1_span.n == "redis"
        assert "custom" not in rs1_span.data
        assert "redis" in rs1_span.data

        assert rs1_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs1_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs1_span.data["redis"]["command"] == "SET"
        assert not rs1_span.data["redis"]["error"]

        assert rs1_span.stack
        assert isinstance(rs1_span.stack, list)
        assert len(rs1_span.stack) > 0

        # Redis span 2
        assert rs2_span.n == "redis"
        assert "custom" not in rs2_span.data
        assert "redis" in rs2_span.data

        assert rs2_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs2_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs2_span.data["redis"]["command"] == "SET"
        assert not rs2_span.data["redis"]["error"]

        assert rs2_span.stack
        assert isinstance(rs2_span.stack, list)
        assert len(rs2_span.stack) > 0

        # Redis span 3
        assert rs3_span.n == "redis"
        assert "custom" not in rs3_span.data
        assert "redis" in rs3_span.data

        assert rs3_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs3_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs3_span.data["redis"]["command"] == "GET"
        assert not rs3_span.data["redis"]["error"]

        assert rs3_span.stack
        assert isinstance(rs3_span.stack, list)
        assert len(rs3_span.stack) > 0

    def test_set_incr_get(self) -> None:
        result = None
        with tracer.start_as_current_span("test"):
            self.client.set("counter", "10")
            self.client.incr("counter")
            result = self.client.get("counter")

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        assert result == b"11"

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert rs1_span.t == test_span.t
        assert rs2_span.t == test_span.t
        assert rs3_span.t == test_span.t

        # Parent relationships
        assert rs1_span.p == test_span.s
        assert rs2_span.p == test_span.s
        assert rs3_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not rs1_span.ec
        assert not rs2_span.ec
        assert not rs3_span.ec

        # Redis span 1
        assert rs1_span.n == "redis"
        assert "custom" not in rs1_span.data
        assert "redis" in rs1_span.data

        assert rs1_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs1_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs1_span.data["redis"]["command"] == "SET"
        assert not rs1_span.data["redis"]["error"]

        assert rs1_span.stack
        assert isinstance(rs1_span.stack, list)
        assert len(rs1_span.stack) > 0

        # Redis span 2
        assert rs2_span.n == "redis"
        assert "custom" not in rs2_span.data
        assert "redis" in rs2_span.data

        assert rs2_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs2_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs2_span.data["redis"]["command"] == "INCRBY"
        assert not rs2_span.data["redis"]["error"]

        assert rs2_span.stack
        assert isinstance(rs2_span.stack, list)
        assert len(rs2_span.stack) > 0

        # Redis span 3
        assert rs3_span.n == "redis"
        assert "custom" not in rs3_span.data
        assert "redis" in rs3_span.data

        assert rs3_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs3_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs3_span.data["redis"]["command"] == "GET"
        assert not rs3_span.data["redis"]["error"]

        assert rs3_span.stack
        assert isinstance(rs3_span.stack, list)
        assert len(rs3_span.stack) > 0

    def test_old_redis_client(self) -> None:
        result = None
        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.set("fooy", "barY")
            result = self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 4

        assert result == b"barX"

        rs1_span = spans[0]
        rs2_span = spans[1]
        rs3_span = spans[2]
        test_span = spans[3]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert rs1_span.t == test_span.t
        assert rs2_span.t == test_span.t
        assert rs3_span.t == test_span.t

        # Parent relationships
        assert rs1_span.p == test_span.s
        assert rs2_span.p == test_span.s
        assert rs3_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not rs1_span.ec
        assert not rs2_span.ec
        assert not rs3_span.ec

        # Redis span 1
        assert rs1_span.n == "redis"
        assert "custom" not in rs1_span.data
        assert "redis" in rs1_span.data

        assert rs1_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs1_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs1_span.data["redis"]["command"] == "SET"
        assert not rs1_span.data["redis"]["error"]

        assert rs1_span.stack
        assert isinstance(rs1_span.stack, list)
        assert len(rs1_span.stack) > 0

        # Redis span 2
        assert rs2_span.n == "redis"
        assert "custom" not in rs2_span.data
        assert "redis" in rs2_span.data

        assert rs2_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs2_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )

        assert rs2_span.data["redis"]["command"] == "SET"
        assert not rs2_span.data["redis"]["error"]

        assert rs2_span.stack
        assert isinstance(rs2_span.stack, list)
        assert len(rs2_span.stack) > 0

        # Redis span 3
        assert rs3_span.n == "redis"
        assert "custom" not in rs3_span.data
        assert "redis" in rs3_span.data

        assert rs3_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs3_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs3_span.data["redis"]["command"] == "GET"
        assert not rs3_span.data["redis"]["error"]

        assert rs3_span.stack
        assert isinstance(rs3_span.stack, list)
        assert len(rs3_span.stack) > 0

    def test_pipelined_requests(self) -> None:
        result = None
        with tracer.start_as_current_span("test"):
            pipe = self.client.pipeline()
            pipe.set("foox", "barX")
            pipe.set("fooy", "barY")
            pipe.get("foox")
            result = pipe.execute()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2

        assert result == [True, True, b"barX"]

        rs1_span = spans[0]
        test_span = spans[1]

        current_span = get_current_span()
        assert not current_span.is_recording()

        # Same traceId
        assert rs1_span.t == test_span.t

        # Parent relationships
        assert rs1_span.p == test_span.s

        # Error logging
        assert not test_span.ec
        assert not rs1_span.ec

        # Redis span 1
        assert rs1_span.n == "redis"
        assert "custom" not in rs1_span.data
        assert "redis" in rs1_span.data

        assert rs1_span.data["redis"]["driver"] == "redis-py"
        assert (
            rs1_span.data["redis"]["connection"]
            == f"redis://{testenv['redis_host']}:6379/0"
        )
        assert rs1_span.data["redis"]["command"] == "PIPELINE"
        assert rs1_span.data["redis"]["subCommands"] == ["SET", "SET", "GET"]
        assert not rs1_span.data["redis"]["error"]

        assert rs1_span.stack
        assert isinstance(rs1_span.stack, list)
        assert len(rs1_span.stack) > 0

    @patch(
        "instana.instrumentation.redis.collect_attributes",
        side_effect=Exception("test-error"),
    )
    @patch("instana.span.span.InstanaSpan.record_exception")
    def test_execute_command_with_instana_exception(self, mock_record_func, _) -> None:
        with tracer.start_as_current_span("test"), pytest.raises(
            Exception, match="test-error"
        ):
            self.client.set("counter", "10")
        mock_record_func.assert_called()

    def test_execute_comand_with_instana_tracing_off(self) -> None:
        with tracer.start_as_current_span("redis"):
            response = self.client.set("counter", "10")
            assert response

    def test_execute_with_instana_tracing_off(self) -> None:
        result = None
        with tracer.start_as_current_span("redis"):
            pipe = self.client.pipeline()
            pipe.set("foox", "barX")
            pipe.set("fooy", "barY")
            pipe.get("foox")
            result = pipe.execute()
            assert result == [True, True, b"barX"]

    def test_execute_with_instana_exception(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="instana")
        with tracer.start_as_current_span("test"), patch(
            "instana.instrumentation.redis.collect_attributes",
            side_effect=Exception("test-error"),
        ):
            pipe = self.client.pipeline()
            pipe.set("foox", "barX")
            pipe.set("fooy", "barY")
            pipe.get("foox")
            pipe.execute()
        assert "Error collecting pipeline commands" in caplog.messages

    def test_ignore_redis(
        self,
    ) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "redis"
        agent.options = StandardOptions()

        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

    def test_ignore_redis_single_command(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "redis:set"
        agent.options = StandardOptions()

        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 2

        redis_get_span = filtered_spans[0]
        sdk_span = filtered_spans[1]

        assert redis_get_span.n == "redis"
        assert redis_get_span.data["redis"]["command"] == "GET"

        assert sdk_span.n == "sdk"

    def test_ignore_redis_multiple_commands(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "redis:set,get"
        agent.options = StandardOptions()
        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 1

        sdk_span = filtered_spans[0]

        assert sdk_span.n == "sdk"

    def test_ignore_redis_with_another_instrumentation(self) -> None:
        os.environ["INSTANA_IGNORE_ENDPOINTS"] = "redis:set;something_else:something"
        agent.options = StandardOptions()
        with tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        assert len(filtered_spans) == 2

        redis_get_span = filtered_spans[0]
        sdk_span = filtered_spans[1]

        assert redis_get_span.n == "redis"
        assert redis_get_span.data["redis"]["command"] == "GET"

        assert sdk_span.n == "sdk"
