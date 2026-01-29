# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020


import logging
import os
from typing import Generator
from unittest.mock import patch

import pytest
import redis

from instana.options import StandardOptions
from instana.singletons import agent, get_tracer
from instana.span.span import get_current_span
from tests.helpers import testenv


class TestRedis:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Clear all spans before a test run"""
        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()
        self.client = redis.Redis(host=testenv["redis_host"], db=testenv["redis_db"])
        yield
        if "INSTANA_IGNORE_ENDPOINTS" in os.environ.keys():
            del os.environ["INSTANA_IGNORE_ENDPOINTS"]
        agent.options.allow_exit_as_root = False
        agent.options = StandardOptions()

    def test_set_get(self) -> None:
        result = None
        with self.tracer.start_as_current_span("test"):
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
        with self.tracer.start_as_current_span("test"):
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
        with self.tracer.start_as_current_span("test"):
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
        with self.tracer.start_as_current_span("test"):
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
        with self.tracer.start_as_current_span("test"), pytest.raises(
            Exception, match="test-error"
        ):
            self.client.set("counter", "10")
        mock_record_func.assert_called()

    def test_execute_comand_with_instana_tracing_off(self) -> None:
        with self.tracer.start_as_current_span("redis"):
            response = self.client.set("counter", "10")
            assert response

    def test_execute_with_instana_tracing_off(self) -> None:
        result = None
        with self.tracer.start_as_current_span("redis"):
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
        with self.tracer.start_as_current_span("test"), patch(
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
        with patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "redis"}):
            agent.options = StandardOptions()

            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3

            filtered_spans = agent.filter_spans(spans)
            assert len(filtered_spans) == 1

    def test_ignore_redis_single_command(self) -> None:
        with patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "redis:set"}):
            agent.options = StandardOptions()

            with self.tracer.start_as_current_span("test"):
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
        with patch.dict(os.environ, {"INSTANA_IGNORE_ENDPOINTS": "redis:set,get"}):
            agent.options = StandardOptions()
            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3

            filtered_spans = agent.filter_spans(spans)
            assert len(filtered_spans) == 1

            sdk_span = filtered_spans[0]

            assert sdk_span.n == "sdk"

    def test_ignore_redis_with_another_instrumentation(self) -> None:
        with patch.dict(
            os.environ,
            {"INSTANA_IGNORE_ENDPOINTS": "redis:set;something_else:something"},
        ):
            agent.options = StandardOptions()
            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3

            filtered_spans = agent.filter_spans(spans)
            assert len(filtered_spans) == 2

            redis_get_span = filtered_spans[0]

            assert redis_get_span.n == "redis"
            assert redis_get_span.data["redis"]["command"] == "GET"

    def test_span_filter_redis_by_command(self) -> None:
        """Test filtering Redis spans by specific command using span_filters."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter Redis SET command",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["SET"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        with self.tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3  # 1 test + 1 SET + 1 GET

        filtered_spans = agent.filter_spans(spans)
        # Should filter out SET command
        assert len(filtered_spans) == 2  # test + GET

        redis_spans = [s for s in filtered_spans if s.n == "redis"]
        assert len(redis_spans) == 1
        assert redis_spans[0].data["redis"]["command"] == "GET"

    def test_span_filter_redis_multiple_commands(self) -> None:
        """Test filtering multiple Redis commands."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter Redis commands",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["SET", "INCRBY"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        with self.tracer.start_as_current_span("test"):
            self.client.set("counter", "10")
            self.client.incr("counter")
            self.client.get("counter")

        spans = self.recorder.queued_spans()
        assert len(spans) == 4  # 1 test + 3 redis

        filtered_spans = agent.filter_spans(spans)
        # Should filter out SET and INCRBY, keep GET
        assert len(filtered_spans) == 2  # test + GET

        redis_spans = [s for s in filtered_spans if s.n == "redis"]
        assert len(redis_spans) == 1
        assert redis_spans[0].data["redis"]["command"] == "GET"

    def test_span_filter_redis_by_category(self) -> None:
        """Test filtering all Redis spans by category."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter all databases",
                    "attributes": [
                        {
                            "key": "category",
                            "values": ["databases"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        with self.tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        # Should filter out all Redis spans
        assert len(filtered_spans) == 1  # Only test span
        assert filtered_spans[0].n == "sdk"

    def test_span_filter_redis_with_include_rule(self) -> None:
        """Test that include rules have precedence over exclude rules."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Exclude all Redis",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                    ],
                }
            ],
            "include": [
                {
                    "name": "Include GET command",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["GET"],
                            "match_type": "strict",
                        },
                    ],
                }
            ],
        }

        with self.tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        # Should keep GET (include rule) and filter out SET (exclude rule)
        assert len(filtered_spans) == 2  # test + GET

        redis_spans = [s for s in filtered_spans if s.n == "redis"]
        assert len(redis_spans) == 1
        assert redis_spans[0].data["redis"]["command"] == "GET"

    def test_span_filter_redis_by_kind(self) -> None:
        """Test filtering Redis spans by kind (exit spans)."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter Redis exit spans",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {"key": "kind", "values": ["exit"], "match_type": "strict"},
                    ],
                }
            ]
        }

        with self.tracer.start_as_current_span("test"):
            self.client.set("foox", "barX")
            self.client.get("foox")

        spans = self.recorder.queued_spans()
        assert len(spans) == 3

        filtered_spans = agent.filter_spans(spans)
        # Should filter out all Redis spans (they are all exit spans)
        assert len(filtered_spans) == 1  # Only test span
        assert filtered_spans[0].n == "sdk"

    def test_span_filter_redis_pipeline(self) -> None:
        """Test filtering Redis PIPELINE command."""
        agent.options.span_filters = {
            "exclude": [
                {
                    "name": "Filter Redis PIPELINE",
                    "attributes": [
                        {"key": "type", "values": ["redis"], "match_type": "strict"},
                        {
                            "key": "redis.command",
                            "values": ["PIPELINE"],
                            "match_type": "strict",
                        },
                    ],
                }
            ]
        }

        with self.tracer.start_as_current_span("test"):
            pipe = self.client.pipeline()
            pipe.set("foox", "barX")
            pipe.set("fooy", "barY")
            pipe.get("foox")
            pipe.execute()

        spans = self.recorder.queued_spans()
        assert len(spans) == 2  # test + pipeline

        filtered_spans = agent.filter_spans(spans)
        # Should filter out PIPELINE command
        assert len(filtered_spans) == 1  # Only test span

    def test_span_filter_redis_with_env_vars(self) -> None:
        """Test filtering Redis spans using INSTANA_TRACING_FILTER_ environment variables."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES": "type;redis|redis.command;SET;strict",
            },
        ):
            # Create new options to pick up env vars
            options = StandardOptions()
            # Set the parsed filters on agent
            agent.options.span_filters = options.span_filters

            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3  # 1 test + 1 SET + 1 GET

            filtered_spans = agent.filter_spans(spans)
            # Should filter out SET command
            assert len(filtered_spans) == 2  # test + GET

            redis_spans = [s for s in filtered_spans if s.n == "redis"]
            assert len(redis_spans) == 1
            assert redis_spans[0].data["redis"]["command"] == "GET"

    def test_span_filter_redis_env_with_match_type(self) -> None:
        """Test filtering Redis spans with match_type using environment variables."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES": "type;redis|redis.command;GET;contains",
            },
        ):
            # Create new options to pick up env vars
            options = StandardOptions()
            # Set the parsed filters on agent
            agent.options.span_filters = options.span_filters

            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3  # 1 test + 1 SET + 1 GET

            filtered_spans = agent.filter_spans(spans)
            # Should filter out GET command (contains match)
            assert len(filtered_spans) == 2  # test + SET

            redis_spans = [s for s in filtered_spans if s.n == "redis"]
            assert len(redis_spans) == 1
            assert redis_spans[0].data["redis"]["command"] == "SET"

    def test_span_filter_redis_env_with_suppression(self) -> None:
        """Test filtering Redis spans with suppression=false using environment variables."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES": "type;redis",
                "INSTANA_TRACING_FILTER_EXCLUDE_0_SUPPRESSION": "false",
            },
        ):
            # Create new options to pick up env vars
            options = StandardOptions()
            # Set the parsed filters on agent
            agent.options.span_filters = options.span_filters

            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3  # 1 test + 2 redis

            filtered_spans = agent.filter_spans(spans)
            # With suppression=false, redis spans should be filtered but test span remains
            assert len(filtered_spans) == 1
            assert filtered_spans[0].n == "sdk"

    def test_span_filter_redis_env_include_rule(self) -> None:
        """Test filtering Redis spans with include rule using environment variables."""
        with patch.dict(
            os.environ,
            {
                "INSTANA_TRACING_FILTER_EXCLUDE_0_ATTRIBUTES": "type;redis",
                "INSTANA_TRACING_FILTER_INCLUDE_0_ATTRIBUTES": "type;redis|redis.command;GET",
            },
        ):
            # Create new options to pick up env vars
            options = StandardOptions()
            # Set the parsed filters on agent
            agent.options.span_filters = options.span_filters

            with self.tracer.start_as_current_span("test"):
                self.client.set("foox", "barX")
                self.client.get("foox")

            spans = self.recorder.queued_spans()
            assert len(spans) == 3  # 1 test + 2 redis

            filtered_spans = agent.filter_spans(spans)
            # Should keep GET (include rule) and filter out SET (exclude rule)
            assert len(filtered_spans) == 2  # test + GET

            redis_spans = [s for s in filtered_spans if s.n == "redis"]
            assert len(redis_spans) == 1
            assert redis_spans[0].data["redis"]["command"] == "GET"

            # Verify test span is also present
            test_spans = [s for s in filtered_spans if s.n == "sdk"]
            assert len(test_spans) == 1
        assert filtered_spans[0].n == "redis"
