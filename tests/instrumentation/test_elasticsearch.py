# (c) Copyright IBM Corp. 2026

"""
Integration tests for Elasticsearch instrumentation
Tests ES 9.x compatibility with real Elasticsearch connection
"""

import contextlib
import os
import pytest
from typing import Generator

from instana.singletons import agent, get_tracer
from instana.span.span import get_current_span
from tests.helpers import testenv


# Check if Elasticsearch is available
try:
    from elasticsearch import Elasticsearch

    elasticsearch_available = True
except ImportError:
    elasticsearch_available = False


@pytest.mark.skipif(
    not elasticsearch_available, reason="elasticsearch-py not installed"
)
class TestElasticsearch:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        """Setup test resources and clear spans before each test"""
        # Disable Elasticsearch client's built-in OpenTelemetry instrumentation
        # to avoid duplicate spans
        os.environ["OTEL_PYTHON_INSTRUMENTATION_ELASTICSEARCH_ENABLED"] = "False"

        # Clear the instrumentation's connection cache so each test starts
        # with a clean state (prevents cluster-discovery spans leaking in).
        from instana.instrumentation.elasticsearch import _connection_cache

        _connection_cache.clear()

        self.tracer = get_tracer()
        self.recorder = self.tracer.span_processor
        self.recorder.clear_spans()

        # Create Elasticsearch client
        self.client = Elasticsearch([
            f"http://{testenv['elasticsearch_host']}:{testenv['elasticsearch_port']}"
        ])

        # Create test index
        self.test_index = "test-instana-es"
        with contextlib.suppress(Exception):
            self.client.indices.delete(
                index=self.test_index,
                ignore_unavailable=True,
            )

        # Warm up the connection so cluster-discovery urllib3 spans don't
        # leak into the test's span count.
        with contextlib.suppress(Exception):
            self.client.info()

        # Clear any spans created during setup
        self.recorder.clear_spans()

        yield

        # Cleanup
        with contextlib.suppress(Exception):
            self.client.indices.delete(
                index=self.test_index,
                ignore_unavailable=True,
            )
        agent.options.allow_exit_as_root = False

    def test_vanilla_search(self) -> None:
        """Test search without tracing context"""
        # Index a document first
        self.client.index(
            index=self.test_index, id="1", document={"name": "test", "value": 100}
        )
        self.client.indices.refresh(index=self.test_index)

        # Search without tracing
        response = self.client.search(
            index=self.test_index, body={"query": {"match_all": {}}}
        )

        # Should have results but no spans
        assert response
        spans = self.recorder.queued_spans()
        assert len(spans) == 0

    def test_basic_search(self) -> None:
        """Test basic search operation with tracing"""
        # Index a document
        with self.tracer.start_as_current_span("test"):
            self.client.index(
                index=self.test_index, id="1", document={"name": "test", "value": 100}
            )
            self.client.indices.refresh(index=self.test_index)

            # Search
            response = self.client.search(
                index=self.test_index, body={"query": {"match_all": {}}}
            )

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 spans are suppressed when the active span is "elasticsearch",
        # so each ES operation produces exactly one elasticsearch span.
        # Total: es_index + es_refresh + es_search + test = 4
        assert len(spans) == 4

        # Filter spans by type
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        urllib3_spans = [s for s in spans if s.n == "urllib3"]
        test_spans = [s for s in spans if s.n == "sdk"]

        assert len(es_spans) == 3  # index, refresh, search
        assert len(urllib3_spans) == 0
        assert len(test_spans) == 1

        search_span = es_spans[2]  # Last ES span is search
        test_span = test_spans[0]

        # Verify span relationships
        assert search_span.t == test_span.t

        # Verify span attributes
        assert search_span.n == "elasticsearch"
        assert not search_span.ec
        assert "elasticsearch" in search_span.data

        es_data = search_span.data["elasticsearch"]
        assert es_data["action"] == "search"
        assert es_data["index"] == self.test_index
        assert "query" in es_data
        assert "hits" in es_data
        assert es_data["hits"] >= 0

    def test_basic_search_as_root_span(self) -> None:
        """Test search as root exit span"""
        agent.options.allow_exit_as_root = True

        # Index a document
        self.client.index(
            index=self.test_index, id="1", document={"name": "test", "value": 100}
        )
        self.client.indices.refresh(index=self.test_index)

        # Search as root span
        response = self.client.search(
            index=self.test_index, body={"query": {"match_all": {}}}
        )

        assert response
        spans = self.recorder.queued_spans()

        # urllib3 spans suppressed under elasticsearch; only ES spans visible
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 3  # index, refresh, search

        search_span = es_spans[2]  # The search operation

        # Root span should have no parent
        assert not search_span.p
        assert not search_span.ec

        # Verify attributes
        assert search_span.n == "elasticsearch"
        es_data = search_span.data["elasticsearch"]
        assert es_data["action"] == "search"
        assert es_data["index"] == self.test_index

    def test_index_document(self) -> None:
        """Test document indexing"""
        with self.tracer.start_as_current_span("test"):
            response = self.client.index(
                index=self.test_index,
                id="doc1",
                document={"field": "value", "number": 42},
            )

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        # Filter spans by type
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        test_spans = [s for s in spans if s.n == "sdk"]

        assert len(es_spans) == 1
        assert len(test_spans) == 1

        es_span = es_spans[0]
        test_span = test_spans[0]

        assert es_span.t == test_span.t
        assert not es_span.ec

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "index"
        assert es_data["index"] == self.test_index
        assert es_data["id"] == "doc1"

    def test_get_document(self) -> None:
        """Test document retrieval"""
        # Index a document first
        self.client.index(index=self.test_index, id="doc1", document={"field": "value"})
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            response = self.client.get(index=self.test_index, id="doc1")

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "get"
        assert es_data["index"] == self.test_index
        assert es_data["id"] == "doc1"

    def test_delete_document(self) -> None:
        """Test document deletion"""
        # Index a document first
        self.client.index(index=self.test_index, id="doc1", document={"field": "value"})
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            response = self.client.delete(index=self.test_index, id="doc1")

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "delete"
        assert es_data["index"] == self.test_index
        assert es_data["id"] == "doc1"

    def test_mget_operation(self) -> None:
        """Test multi-get operation"""
        # Index multiple documents
        for i in range(1, 4):
            self.client.index(
                index=self.test_index,
                id=str(i),
                document={"name": f"doc{i}", "value": i * 10},
            )
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            response = self.client.mget(
                body={
                    "docs": [
                        {"_index": self.test_index, "_id": "1"},
                        {"_index": self.test_index, "_id": "2"},
                        {"_index": self.test_index, "_id": "3"},
                    ]
                }
            )

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "mget"
        assert es_data["index"] == self.test_index
        assert "1,2,3" in es_data["id"]
        assert "mget.found" in es_data
        assert es_data["mget.found"] == 3

    def test_msearch_operation(self) -> None:
        """Test multi-search operation"""
        # Index documents in multiple indices
        for idx in ["index1", "index2"]:
            self.client.index(
                index=f"{self.test_index}-{idx}",
                id="1",
                document={"name": "test", "value": 100},
            )
            self.client.indices.refresh(index=f"{self.test_index}-{idx}")

        with self.tracer.start_as_current_span("test"):
            response = self.client.msearch(
                body=[
                    {"index": f"{self.test_index}-index1"},
                    {"query": {"match_all": {}}},
                    {"index": f"{self.test_index}-index2"},
                    {"query": {"match_all": {}}},
                ]
            )

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "msearch"
        assert "index1" in es_data["index"]
        assert "index2" in es_data["index"]
        assert "msearch.success" in es_data
        assert es_data["msearch.success"] >= 0

    def test_bulk_operation(self) -> None:
        """Test bulk operation"""
        with self.tracer.start_as_current_span("test"):
            response = self.client.bulk(
                body=[
                    {"index": {"_index": self.test_index, "_id": "1"}},
                    {"field": "value1"},
                    {"index": {"_index": self.test_index, "_id": "2"}},
                    {"field": "value2"},
                    {"delete": {"_index": self.test_index, "_id": "3"}},
                ]
            )

        assert response
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        assert es_span.n == "elasticsearch"
        es_data = es_span.data["elasticsearch"]
        assert es_data["action"] == "bulk"
        assert es_data["index"] == self.test_index
        assert "bulk.size" in es_data
        assert es_data["bulk.size"] == 3
        assert "index" in es_data["bulk.operations"]
        assert "delete" in es_data["bulk.operations"]

    def test_error_capture(self) -> None:
        """Test error handling and capture"""
        try:
            with self.tracer.start_as_current_span("test"):
                # Try to get non-existent document
                self.client.get(index=self.test_index, id="nonexistent")
        except Exception:
            pass

        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]

        # record_exception() increments ec; elasticsearch.error also sets it → ec >= 1
        assert es_span.ec >= 1
        assert "elasticsearch" in es_span.data
        assert "error" in es_span.data["elasticsearch"]

    def test_connection_info(self) -> None:
        """Test connection information capture"""
        # First create the index
        self.client.index(index=self.test_index, id="1", document={"test": "data"})
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            self.client.search(index=self.test_index, body={"query": {"match_all": {}}})

        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]
        es_data = es_span.data["elasticsearch"]

        # Should have connection info
        assert "address" in es_data
        assert "port" in es_data
        # Cluster name might be available depending on ES setup
        # assert "cluster" in es_data

    def test_query_shortening(self) -> None:
        """Test that long queries are shortened"""
        # Create a very long query
        long_query = {
            "query": {
                "bool": {
                    "should": [{"match": {"field": f"value{i}"}} for i in range(100)]
                }
            }
        }

        with self.tracer.start_as_current_span("test"), contextlib.suppress(Exception):
            self.client.search(index=self.test_index, body=long_query)

        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_span = es_spans[0]
        es_data = es_span.data["elasticsearch"]

        # Query should be present but shortened
        assert "query" in es_data
        query_str = es_data["query"]
        # Should be truncated to max 1000 chars + "..."
        assert len(query_str) <= 1003

    def test_multiple_operations(self) -> None:
        """Test multiple operations in sequence"""
        with self.tracer.start_as_current_span("test"):
            # Index
            self.client.index(index=self.test_index, id="1", document={"name": "test"})
            # Get
            self.client.get(index=self.test_index, id="1")
            # Search
            self.client.search(index=self.test_index, body={"query": {"match_all": {}}})
            # Delete
            self.client.delete(index=self.test_index, id="1")

        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: 4 es_spans + test span = 5
        assert len(spans) == 5

        # Filter spans by type
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        test_spans = [s for s in spans if s.n == "sdk"]

        assert len(es_spans) == 4  # index, get, search, delete
        assert len(test_spans) == 1

        test_span = test_spans[0]

        # Verify all ES spans have correct trace ID
        for es_span in es_spans:
            assert es_span.t == test_span.t
            assert es_span.n == "elasticsearch"

    def test_update_operation(self) -> None:
        """Test update operation — covers _update URL action detection"""
        self.client.index(index=self.test_index, id="1", document={"field": "value"})

        with self.tracer.start_as_current_span("test"):
            self.client.update(
                index=self.test_index, id="1", body={"doc": {"field": "updated"}}
            )

        spans = self.recorder.queued_spans()
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        assert es_spans[0].data["elasticsearch"]["action"] == "update"

    def test_mget_with_ids_array(self) -> None:
        """Test mget with 'ids' array body — covers process_mget_params ids path"""
        for i in range(1, 4):
            self.client.index(index=self.test_index, id=str(i), document={"v": i})
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            response = self.client.mget(
                index=self.test_index,
                body={"ids": ["1", "2", "3"]},
            )

        assert response
        spans = self.recorder.queued_spans()
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_data = es_spans[0].data["elasticsearch"]
        assert es_data["action"] == "mget"
        assert "id" in es_data

    def test_mget_with_many_ids(self) -> None:
        """Test mget with >10 docs — covers the id truncation path"""
        for i in range(1, 13):
            self.client.index(index=self.test_index, id=str(i), document={"v": i})
        self.client.indices.refresh(index=self.test_index)

        with self.tracer.start_as_current_span("test"):
            response = self.client.mget(
                body={
                    "docs": [
                        {"_index": self.test_index, "_id": str(i)} for i in range(1, 13)
                    ]
                }
            )

        assert response
        spans = self.recorder.queued_spans()
        es_spans = [s for s in spans if s.n == "elasticsearch"]
        assert len(es_spans) == 1
        es_data = es_spans[0].data["elasticsearch"]
        assert "total)" in es_data["id"]

    def test_search_with_string_body(self) -> None:
        """Test search with pre-serialised string body — covers str body path"""
        import json as _json

        self.client.index(index=self.test_index, id="1", document={"name": "test"})
        self.client.indices.refresh(index=self.test_index)

        query_str = _json.dumps({"query": {"match_all": {}}})

        with self.tracer.start_as_current_span("test"):
            # Pass the body as a raw string so the str branch is exercised.
            # ES 9.x accepts it through the params kwarg workaround below.
            # We exercise the code path by calling extract_params_from_request
            # directly since the high-level client always serialises to dict.
            from instana.instrumentation.elasticsearch import (
                extract_params_from_request,
            )
            from unittest.mock import MagicMock

            mock_span = MagicMock()
            extract_params_from_request(mock_span, "GET", "/_search", None, query_str)
            mock_span.set_attribute.assert_any_call("elasticsearch.query", query_str)

    def test_search_with_non_dict_body(self) -> None:
        """Covers the else branch of the body type check in extract_params_from_request"""
        from instana.instrumentation.elasticsearch import extract_params_from_request
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        # Pass an arbitrary non-dict, non-str body
        extract_params_from_request(mock_span, "GET", "/_search", None, 42)
        mock_span.set_attribute.assert_any_call("elasticsearch.query", "42")

    def test_params_index_and_id_fallback(self) -> None:
        """Covers params-based index/id extraction when URL has no index/id"""
        from instana.instrumentation.elasticsearch import extract_params_from_request
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        extract_params_from_request(
            mock_span,
            "GET",
            "/_doc/doc1",
            {"index": "my-index", "id": "doc1"},
            None,
        )
        mock_span.set_attribute.assert_any_call("elasticsearch.index", "my-index")
        # elasticsearch.type is no longer emitted (removed in ES 8.x+)
        calls = [str(c) for c in mock_span.set_attribute.call_args_list]
        assert not any("elasticsearch.type" in c for c in calls)

    def test_bulk_with_string_body(self) -> None:
        """Test bulk with newline-delimited JSON string body — covers str body path"""
        import json as _json

        ndjson = "\n".join([
            _json.dumps({"index": {"_index": self.test_index, "_id": "1"}}),
            _json.dumps({"field": "value1"}),
            _json.dumps({"index": {"_index": self.test_index, "_id": "2"}}),
            _json.dumps({"field": "value2"}),
        ])

        with self.tracer.start_as_current_span("test"):
            from instana.instrumentation.elasticsearch import process_bulk_params
            from unittest.mock import MagicMock

            mock_span = MagicMock()
            process_bulk_params(mock_span, ndjson)
            mock_span.set_attribute.assert_any_call("elasticsearch.bulk.size", 2)

    def test_msearch_with_string_body(self) -> None:
        """Test msearch with newline-delimited JSON string — covers str body path"""
        import json as _json

        ndjson = "\n".join([
            _json.dumps({"index": f"{self.test_index}-index1"}),
            _json.dumps({"query": {"match_all": {}}}),
        ])

        from instana.instrumentation.elasticsearch import process_msearch_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        process_msearch_params(mock_span, ndjson)
        mock_span.set_attribute.assert_any_call(
            "elasticsearch.index", f"{self.test_index}-index1"
        )

    def test_http_500_error_sets_span_error(self) -> None:
        """Covers the HTTP 5xx branch in perform_request_with_instana"""
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.meta.status = 503
        mock_response.body = {}

        with (
            self.tracer.start_as_current_span("test"),
            patch(
                "elasticsearch._sync.client._base.BaseClient.perform_request",
                wraps=lambda *a, **kw: mock_response,
            ),
        ):
            pass  # just verify the span error branch is reachable via unit path

        # Verify via direct unit call instead
        from instana.instrumentation.elasticsearch import perform_request_with_instana
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_span.__enter__ = lambda s: mock_span
        mock_span.__exit__ = MagicMock(return_value=False)

        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        mock_response = MagicMock()
        mock_response.meta.status = 503

        with (
            patch("instana.instrumentation.elasticsearch.get_tracer_tuple") as mock_gt,
            patch("instana.instrumentation.elasticsearch.get_current"),
            patch("instana.instrumentation.elasticsearch.collect_connection_info"),
            patch("instana.instrumentation.elasticsearch.extract_params_from_request"),
            patch("instana.instrumentation.elasticsearch.extract_response_metadata"),
        ):
            mock_gt.return_value = (mock_tracer, None, None)
            wrapped = MagicMock(return_value=mock_response)
            instance = MagicMock()
            perform_request_with_instana(wrapped, instance, ("GET", "/test"), {})

        mock_span.set_attribute.assert_any_call("elasticsearch.error", "HTTP 503")

    def test_extract_response_metadata_int_total(self) -> None:
        """Covers the isinstance(total, int) branch in extract_response_metadata"""
        from instana.instrumentation.elasticsearch import extract_response_metadata
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_response = MagicMock()
        mock_response.body = {"hits": {"total": 5, "hits": []}}
        extract_response_metadata(mock_span, mock_response)
        mock_span.set_attribute.assert_any_call("elasticsearch.hits", 5)

    def test_extract_response_metadata_msearch_errors(self) -> None:
        """Covers msearch error_count branch in extract_response_metadata"""
        from instana.instrumentation.elasticsearch import extract_response_metadata
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_response = MagicMock()
        mock_response.body = {
            "responses": [
                {"hits": {"total": {"value": 1}, "hits": []}},
                {"error": {"type": "index_not_found_exception"}},
            ]
        }
        extract_response_metadata(mock_span, mock_response)
        mock_span.set_attribute.assert_any_call("elasticsearch.msearch.errors", 1)
        mock_span.set_attribute.assert_any_call("elasticsearch.msearch.success", 1)

    def test_extract_response_metadata_mget_not_found(self) -> None:
        """Covers mget not_found_count branch in extract_response_metadata"""
        from instana.instrumentation.elasticsearch import extract_response_metadata
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_response = MagicMock()
        mock_response.body = {
            "docs": [
                {"found": True},
                {"found": False},
                {"found": False},
            ]
        }
        extract_response_metadata(mock_span, mock_response)
        mock_span.set_attribute.assert_any_call("elasticsearch.mget.found", 1)
        mock_span.set_attribute.assert_any_call("elasticsearch.mget.not_found", 2)

    def test_msearch_with_int_total_per_response(self) -> None:
        """Covers msearch int total branch in extract_response_metadata"""
        from instana.instrumentation.elasticsearch import extract_response_metadata
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_response = MagicMock()
        mock_response.body = {
            "responses": [
                {"hits": {"total": 3, "hits": []}},
            ]
        }
        extract_response_metadata(mock_span, mock_response)
        mock_span.set_attribute.assert_any_call("elasticsearch.hits", 3)

    def test_current_span_cleanup(self) -> None:
        """Test that current span is properly cleaned up"""
        # First create the index and add a document
        self.client.index(index=self.test_index, id="1", document={"name": "test"})
        self.client.indices.refresh(index=self.test_index)
        self.recorder.clear_spans()

        with self.tracer.start_as_current_span("test"), contextlib.suppress(Exception):
            self.client.search(index=self.test_index, body={"query": {"match_all": {}}})

        # After context, current span should not be recording
        current_span = get_current_span()
        assert not current_span.is_recording()

        # Verify spans were created
        spans = self.recorder.queued_spans()
        # urllib3 suppressed under elasticsearch: es_span + test span = 2
        assert len(spans) == 2

    def test_unit_to_string_es_multi_parameter(self) -> None:
        """Covers empty-string → '_all' and list branches"""
        from instana.instrumentation.elasticsearch import to_string_es_multi_parameter

        assert to_string_es_multi_parameter("") == "_all"
        assert to_string_es_multi_parameter(["a", "b"]) == "a,b"
        assert to_string_es_multi_parameter(None) is None
        assert to_string_es_multi_parameter("hello") == "hello"
        assert to_string_es_multi_parameter(42) == "42"

    def test_unit_detect_action_mapping_settings(self) -> None:
        """Covers /_mapping and /_settings URL action detection"""
        from instana.instrumentation.elasticsearch import detect_action_from_url

        assert (
            detect_action_from_url("PUT", "/my-index/_mapping") == "indices.putMapping"
        )
        assert (
            detect_action_from_url("GET", "/my-index/_mapping") == "indices.getMapping"
        )
        assert (
            detect_action_from_url("PUT", "/my-index/_settings")
            == "indices.putSettings"
        )
        assert (
            detect_action_from_url("GET", "/my-index/_settings")
            == "indices.getSettings"
        )

    def test_unit_process_mget_params_type_field_ignored(self) -> None:
        """_type field in docs is silently ignored (removed in ES 8.x+)"""
        from instana.instrumentation.elasticsearch import process_mget_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        process_mget_params(
            mock_span,
            body={
                "docs": [
                    {"_index": "idx", "_type": "my_type", "_id": "1"},
                ]
            },
        )
        # index and id should still be captured; type must not be emitted
        mock_span.set_attribute.assert_any_call("elasticsearch.index", "idx")
        mock_span.set_attribute.assert_any_call("elasticsearch.id", "1")
        calls = [str(c) for c in mock_span.set_attribute.call_args_list]
        assert not any("elasticsearch.type" in c for c in calls)

    def test_unit_process_msearch_params_empty_body(self) -> None:
        """Covers process_msearch_params with None/empty body"""
        from instana.instrumentation.elasticsearch import process_msearch_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        process_msearch_params(mock_span, None)
        mock_span.set_attribute.assert_not_called()

    def test_unit_process_msearch_params_bad_json_line(self) -> None:
        """Covers json.JSONDecodeError continue branch in process_msearch_params"""
        from instana.instrumentation.elasticsearch import process_msearch_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        # Mix of valid and invalid JSON lines
        ndjson = '{"index": "my-index"}\nNOT_JSON\n{"query": {"match_all": {}}}'
        process_msearch_params(mock_span, ndjson)
        # Should not raise; index should still be extracted from the valid header line
        mock_span.set_attribute.assert_any_call("elasticsearch.index", "my-index")

    def test_unit_process_bulk_params_non_list_body(self) -> None:
        """Covers the else/return branch when body is not str or list"""
        from instana.instrumentation.elasticsearch import process_bulk_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        process_bulk_params(mock_span, 12345)  # int body → should return early
        mock_span.set_attribute.assert_not_called()

    def test_unit_process_bulk_params_bad_json_line(self) -> None:
        """Covers json.JSONDecodeError continue branch in process_bulk_params"""
        import json as _json
        from instana.instrumentation.elasticsearch import process_bulk_params
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        ndjson = "\n".join([
            _json.dumps({"index": {"_index": "my-index", "_id": "1"}}),
            "NOT_JSON",
            _json.dumps({"field": "value"}),
        ])
        process_bulk_params(mock_span, ndjson)
        # Should not raise and should count the valid action line
        mock_span.set_attribute.assert_any_call("elasticsearch.bulk.size", 1)

    def test_unit_collect_connection_info_no_connection_id(self) -> None:
        """Covers the early-return when get_connection_id returns None"""
        from instana.instrumentation.elasticsearch import collect_connection_info
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        instance = MagicMock(spec=[])  # no 'transport' attribute
        collect_connection_info(mock_span, instance)
        mock_span.set_attribute.assert_not_called()

    def test_unit_discover_cluster_name_cached_ttl(self) -> None:
        """Covers the cached cluster_name TTL-hit return path"""
        import time
        from instana.instrumentation.elasticsearch import (
            _connection_cache,
            discover_cluster_name,
        )
        from unittest.mock import MagicMock

        conn_id = "test-host:9999"
        _connection_cache[conn_id] = {
            "cluster_name": "my-cluster",
            "last_updated": time.time(),
        }
        try:
            instance = MagicMock()
            result = discover_cluster_name(instance, conn_id)
            assert result == "my-cluster"
            # instance.info() should NOT have been called (cache hit)
            instance.info.assert_not_called()
        finally:
            _connection_cache.pop(conn_id, None)

    def test_endpoint_attribute_set_on_span(self) -> None:
        """elasticsearch.endpoint is set to the URL path for backend label fallback"""
        from instana.instrumentation.elasticsearch import perform_request_with_instana
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.meta.status = 200
        mock_response.body = {}

        mock_span = MagicMock()
        mock_span.__enter__ = lambda s: mock_span
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("instana.instrumentation.elasticsearch.get_tracer_tuple") as mock_gt,
            patch("instana.instrumentation.elasticsearch.get_current"),
            patch("instana.instrumentation.elasticsearch.collect_connection_info"),
            patch("instana.instrumentation.elasticsearch.extract_params_from_request"),
            patch("instana.instrumentation.elasticsearch.extract_response_metadata"),
        ):
            mock_gt.return_value = (mock_tracer, None, None)
            wrapped = MagicMock(return_value=mock_response)
            perform_request_with_instana(
                wrapped, MagicMock(), ("GET", "/my-index/_search"), {}
            )

        mock_span.set_attribute.assert_any_call(
            "elasticsearch.endpoint", "/my-index/_search"
        )
        mock_span.set_attribute.assert_any_call(
            "elasticsearch.url", "/my-index/_search"
        )

    def test_cluster_fallback_not_set_when_cluster_absent(self) -> None:
        """When cluster name cannot be discovered, elasticsearch.cluster must NOT be set
        (backend uses address+port for destination resolution instead)"""
        from instana.instrumentation.elasticsearch import collect_connection_info
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()

        mock_cfg = MagicMock()
        mock_cfg.host = "localhost"
        mock_cfg.port = 9200

        mock_node = MagicMock()
        mock_node.config = mock_cfg

        mock_pool = MagicMock()
        mock_pool.all.return_value = [mock_node]

        mock_transport = MagicMock()
        mock_transport.node_pool = mock_pool

        mock_instance = MagicMock()
        mock_instance.transport = mock_transport

        with patch(
            "instana.instrumentation.elasticsearch.discover_cluster_name",
            return_value=None,
        ):
            collect_connection_info(mock_span, mock_instance)

        calls = [str(c) for c in mock_span.set_attribute.call_args_list]
        assert any("elasticsearch.address" in c for c in calls)
        assert any("elasticsearch.port" in c for c in calls)
        # cluster must NOT be set when discovery fails
        assert not any("elasticsearch.cluster" in c for c in calls)

    def test_port_is_integer(self) -> None:
        """elasticsearch.port must be sent as integer, not string"""
        from instana.instrumentation.elasticsearch import collect_connection_info
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()

        mock_cfg = MagicMock()
        mock_cfg.host = "localhost"
        mock_cfg.port = 9200

        mock_node = MagicMock()
        mock_node.config = mock_cfg

        mock_pool = MagicMock()
        mock_pool.all.return_value = [mock_node]

        mock_transport = MagicMock()
        mock_transport.node_pool = mock_pool

        mock_instance = MagicMock()
        mock_instance.transport = mock_transport

        with patch(
            "instana.instrumentation.elasticsearch.discover_cluster_name",
            return_value=None,
        ):
            collect_connection_info(mock_span, mock_instance)

        port_calls = [
            c
            for c in mock_span.set_attribute.call_args_list
            if "elasticsearch.port" in str(c)
        ]
        assert len(port_calls) == 1
        _, port_value = port_calls[0].args
        assert isinstance(port_value, int), (
            f"port should be int, got {type(port_value)}"
        )
        assert port_value == 9200

    def test_msearch_hits_zero_is_recorded(self) -> None:
        """elasticsearch.hits must be set even when total_hits == 0"""
        from instana.instrumentation.elasticsearch import extract_response_metadata
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_response = MagicMock()
        mock_response.body = {
            "responses": [
                {"hits": {"total": {"value": 0}, "hits": []}},
            ]
        }
        extract_response_metadata(mock_span, mock_response)
        mock_span.set_attribute.assert_any_call("elasticsearch.hits", 0)


@pytest.mark.skipif(
    not elasticsearch_available, reason="elasticsearch-py not installed"
)
class TestElasticsearchAsync:
    """Unit tests for async Elasticsearch instrumentation (mock-only, no live server)."""

    def test_async_wrapper_is_registered(self) -> None:
        """async_perform_request_with_instana must be importable after module load"""
        from instana.instrumentation.elasticsearch import (
            async_perform_request_with_instana,
        )
        import inspect

        assert inspect.iscoroutinefunction(async_perform_request_with_instana)

    def test_async_collect_connection_info_is_coroutine(self) -> None:
        """_async_collect_connection_info must be a coroutine function"""
        from instana.instrumentation.elasticsearch import _async_collect_connection_info
        import inspect

        assert inspect.iscoroutinefunction(_async_collect_connection_info)

    def test_async_discover_cluster_name_is_coroutine(self) -> None:
        """_async_discover_cluster_name must be a coroutine function"""
        from instana.instrumentation.elasticsearch import _async_discover_cluster_name
        import inspect

        assert inspect.iscoroutinefunction(_async_discover_cluster_name)

    def test_async_discover_cluster_name_cache_hit(self) -> None:
        """Returns cached cluster name without calling instance.info()"""
        import asyncio
        import time
        from instana.instrumentation.elasticsearch import (
            _connection_cache,
            _async_discover_cluster_name,
        )
        from unittest.mock import AsyncMock, MagicMock

        conn_id = "async-host:9200"
        _connection_cache[conn_id] = {
            "cluster_name": "async-cluster",
            "last_updated": time.time(),
        }
        try:
            instance = MagicMock()
            instance.info = AsyncMock()
            result = asyncio.run(_async_discover_cluster_name(instance, conn_id))
            assert result == "async-cluster"
            instance.info.assert_not_called()
        finally:
            _connection_cache.pop(conn_id, None)

    def test_async_discover_cluster_name_live_call(self) -> None:
        """Calls instance.info() and extracts cluster_name from body"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            _connection_cache,
            _async_discover_cluster_name,
        )
        from unittest.mock import AsyncMock, MagicMock

        conn_id = "async-host:9201"
        _connection_cache.pop(conn_id, None)

        mock_info_response = MagicMock()
        mock_info_response.body = {"cluster_name": "live-cluster", "version": {}}

        instance = MagicMock()
        instance.info = AsyncMock(return_value=mock_info_response)

        try:
            result = asyncio.run(_async_discover_cluster_name(instance, conn_id))
            assert result == "live-cluster"
            assert _connection_cache[conn_id]["cluster_name"] == "live-cluster"
        finally:
            _connection_cache.pop(conn_id, None)

    def test_async_collect_connection_info_cache_hit(self) -> None:
        """Uses cached host/port/cluster when available"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            _connection_cache,
            _async_collect_connection_info,
        )
        from unittest.mock import MagicMock

        conn_id = "cached-host:9200"
        _connection_cache[conn_id] = {
            "host": "cached-host",
            "port": 9200,
            "cluster_name": "cached-cluster",
        }
        try:
            mock_span = MagicMock()

            mock_cfg = MagicMock()
            mock_cfg.host = "cached-host"
            mock_cfg.port = 9200
            mock_node = MagicMock()
            mock_node.config = mock_cfg
            mock_pool = MagicMock()
            mock_pool.all.return_value = [mock_node]
            mock_transport = MagicMock()
            mock_transport.node_pool = mock_pool
            instance = MagicMock()
            instance.transport = mock_transport

            asyncio.run(_async_collect_connection_info(mock_span, instance))

            mock_span.set_attribute.assert_any_call(
                "elasticsearch.address", "cached-host"
            )
            mock_span.set_attribute.assert_any_call("elasticsearch.port", 9200)
            mock_span.set_attribute.assert_any_call(
                "elasticsearch.cluster", "cached-cluster"
            )
        finally:
            _connection_cache.pop(conn_id, None)

    def test_async_cluster_fallback_not_set_when_cluster_absent(self) -> None:
        """cluster must NOT be set when async discovery fails"""
        import asyncio
        from instana.instrumentation.elasticsearch import _async_collect_connection_info
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_span = MagicMock()

        mock_cfg = MagicMock()
        mock_cfg.host = "localhost"
        mock_cfg.port = 9200
        mock_node = MagicMock()
        mock_node.config = mock_cfg
        mock_pool = MagicMock()
        mock_pool.all.return_value = [mock_node]
        mock_transport = MagicMock()
        mock_transport.node_pool = mock_pool
        instance = MagicMock()
        instance.transport = mock_transport

        with patch(
            "instana.instrumentation.elasticsearch._async_discover_cluster_name",
            new=AsyncMock(return_value=None),
        ):
            asyncio.run(_async_collect_connection_info(mock_span, instance))

        calls = [str(c) for c in mock_span.set_attribute.call_args_list]
        assert any("elasticsearch.address" in c for c in calls)
        assert any("elasticsearch.port" in c for c in calls)
        assert not any("elasticsearch.cluster" in c for c in calls)

    def test_async_perform_request_no_tracer(self) -> None:
        """Returns bare await when tracer is unavailable"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            async_perform_request_with_instana,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        expected = MagicMock()
        wrapped = AsyncMock(return_value=expected)

        with patch(
            "instana.instrumentation.elasticsearch.get_tracer_tuple",
            return_value=(None, None, None),
        ):
            result = asyncio.run(
                async_perform_request_with_instana(
                    wrapped, MagicMock(), ("GET", "/test"), {}
                )
            )

        assert result is expected
        wrapped.assert_awaited_once()

    def test_async_perform_request_recursive_guard(self) -> None:
        """Skips instrumentation when span_name is 'elasticsearch'"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            async_perform_request_with_instana,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        expected = MagicMock()
        wrapped = AsyncMock(return_value=expected)

        with patch(
            "instana.instrumentation.elasticsearch.get_tracer_tuple",
            return_value=(MagicMock(), None, "elasticsearch"),
        ):
            result = asyncio.run(
                async_perform_request_with_instana(
                    wrapped, MagicMock(), ("GET", "/test"), {}
                )
            )

        assert result is expected
        wrapped.assert_awaited_once()

    def test_async_perform_request_creates_span(self) -> None:
        """Full happy-path: span created, endpoint/url set, response returned"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            async_perform_request_with_instana,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.meta.status = 200
        mock_response.body = {}

        mock_span = MagicMock()
        mock_span.__enter__ = lambda s: mock_span
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch(
                "instana.instrumentation.elasticsearch.get_tracer_tuple",
                return_value=(mock_tracer, None, None),
            ),
            patch("instana.instrumentation.elasticsearch.get_current"),
            patch(
                "instana.instrumentation.elasticsearch._async_collect_connection_info",
                new=AsyncMock(),
            ),
            patch("instana.instrumentation.elasticsearch.extract_params_from_request"),
            patch("instana.instrumentation.elasticsearch.extract_response_metadata"),
        ):
            wrapped = AsyncMock(return_value=mock_response)
            result = asyncio.run(
                async_perform_request_with_instana(
                    wrapped, MagicMock(), ("GET", "/my-index/_search"), {}
                )
            )

        assert result is mock_response
        mock_span.set_attribute.assert_any_call(
            "elasticsearch.endpoint", "/my-index/_search"
        )
        mock_span.set_attribute.assert_any_call(
            "elasticsearch.url", "/my-index/_search"
        )

    def test_async_perform_request_500_sets_error(self) -> None:
        """HTTP 5xx response sets elasticsearch.error on the span"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            async_perform_request_with_instana,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_response = MagicMock()
        mock_response.meta.status = 503
        mock_response.body = {}

        mock_span = MagicMock()
        mock_span.__enter__ = lambda s: mock_span
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch(
                "instana.instrumentation.elasticsearch.get_tracer_tuple",
                return_value=(mock_tracer, None, None),
            ),
            patch("instana.instrumentation.elasticsearch.get_current"),
            patch(
                "instana.instrumentation.elasticsearch._async_collect_connection_info",
                new=AsyncMock(),
            ),
            patch("instana.instrumentation.elasticsearch.extract_params_from_request"),
            patch("instana.instrumentation.elasticsearch.extract_response_metadata"),
        ):
            wrapped = AsyncMock(return_value=mock_response)
            asyncio.run(
                async_perform_request_with_instana(
                    wrapped, MagicMock(), ("GET", "/test"), {}
                )
            )

        mock_span.set_attribute.assert_any_call("elasticsearch.error", "HTTP 503")

    def test_async_perform_request_exception_recorded(self) -> None:
        """Exception raised by wrapped call is recorded on the span and re-raised"""
        import asyncio
        from instana.instrumentation.elasticsearch import (
            ELASTICSEARCH_ERROR_ATTRIBUTE,
            async_perform_request_with_instana,
        )
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_span = MagicMock()
        mock_span.__enter__ = lambda s: mock_span
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer = MagicMock()
        mock_tracer.start_as_current_span.return_value = mock_span

        boom = RuntimeError("connection refused")

        with (
            patch(
                "instana.instrumentation.elasticsearch.get_tracer_tuple",
                return_value=(mock_tracer, None, None),
            ),
            patch("instana.instrumentation.elasticsearch.get_current"),
            patch(
                "instana.instrumentation.elasticsearch._async_collect_connection_info",
                new=AsyncMock(),
            ),
            patch("instana.instrumentation.elasticsearch.extract_params_from_request"),
            pytest.raises(RuntimeError, match="connection refused"),
        ):
            wrapped = AsyncMock(side_effect=boom)
            asyncio.run(
                async_perform_request_with_instana(
                    wrapped, MagicMock(), ("GET", "/test"), {}
                )
            )

        mock_span.record_exception.assert_called_once_with(boom)
        mock_span.set_attribute.assert_any_call(
            ELASTICSEARCH_ERROR_ATTRIBUTE, "connection refused"
        )


# Made with Bob
