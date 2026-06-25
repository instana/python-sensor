# (c) Copyright IBM Corp. 2026

"""
Elasticsearch instrumentation
Supports both sync and async clients for elasticsearch
"""

try:
    import json
    import re
    import time
    from collections import defaultdict
    from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional, Union

    if TYPE_CHECKING:
        from instana.span.span import InstanaSpan
        from elasticsearch import AsyncElasticsearch, Elasticsearch
        from elastic_transport import ObjectApiResponse

    import elasticsearch  # noqa: F401
    import wrapt
    from opentelemetry.context import get_current
    from instana.log import logger
    from instana.util.traceutils import get_tracer_tuple

    ELASTICSEARCH_INDEX_ATTRIBUTE = "elasticsearch.index"
    ELASTICSEARCH_ID_ATTRIBUTE = "elasticsearch.id"
    ELASTICSEARCH_HITS_ATTRIBUTE = "elasticsearch.hits"
    ELASTICSEARCH_ERROR_ATTRIBUTE = "elasticsearch.error"

    # Regex patterns for URL parsing
    DOCUMENT_ID_PATTERN = re.compile(r"^/[^/]+/_doc/([^/?]+)")
    INDEX_PATTERN = re.compile(r"^/([^/?]+)")

    # Map URL _keyword segments to action names (for GET/HEAD/DELETE/other methods)
    _URL_KEYWORD_ACTION: dict[str, str] = {
        "_msearch": "msearch",
        "_mget": "mget",
        "_bulk": "bulk",
        "_search": "search",
        "_update": "update",
        "_mapping": "indices.getMapping",
        "_settings": "indices.getSettings",
    }
    # Keywords whose action depends on the HTTP method
    _URL_KEYWORD_METHOD_ACTION: dict[str, dict[str, str]] = {
        "_doc": {"POST": "index", "PUT": "index", "GET": "get", "DELETE": "delete"},
        "_create": {"POST": "index", "PUT": "index"},
        "_mapping": {"PUT": "indices.putMapping"},
        "_settings": {"PUT": "indices.putSettings"},
    }

    # Connection cache to avoid repeated URL parsing and store cluster info
    # Structure: {connection_id: {host, port, cluster_name, last_updated}}
    _connection_cache: defaultdict[str, dict[str, Any]] = defaultdict(dict)

    # Cluster name cache TTL (5 minutes)
    CLUSTER_NAME_CACHE_TTL = 300

    def get_connection_id(
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
    ) -> Optional[str]:
        """
        Generate a unique connection ID for caching.
        Uses host:port as identifier via elastic-transport node_pool.
        """
        try:
            if hasattr(instance, "transport"):
                transport = instance.transport
                if hasattr(transport, "node_pool"):
                    nodes = list(transport.node_pool.all())
                    if nodes:
                        cfg = nodes[0].config
                        return f"{cfg.host}:{cfg.port}"
        except Exception:
            logger.debug("get_connection_id error:", exc_info=True)
        return None

    def _get_cached_cluster_name(connection_id: str) -> Optional[str]:
        """Return cached cluster name if still within TTL, otherwise None."""
        cached = _connection_cache[connection_id]
        cluster_name = cached.get("cluster_name")
        if (
            cluster_name
            and (time.time() - cached.get("last_updated", 0)) < CLUSTER_NAME_CACHE_TTL
        ):
            return cluster_name
        return None

    def _store_cluster_name(connection_id: str, cluster_name: str) -> None:
        """Persist a discovered cluster name into the connection cache."""
        _connection_cache[connection_id]["cluster_name"] = cluster_name
        _connection_cache[connection_id]["last_updated"] = time.time()

    def _extract_cluster_name_from_response(
        info_response: "ObjectApiResponse[Any]",
    ) -> Optional[str]:
        """Pull cluster_name out of an ES info() response object."""
        if hasattr(info_response, "body"):
            body = getattr(info_response, "body", None)
            if isinstance(body, dict):
                return body.get("cluster_name")
        return None

    def discover_cluster_name(
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
        connection_id: str,
    ) -> Optional[str]:
        """
        Discover Elasticsearch cluster name by calling cluster info API (sync).
        Caches result with TTL to avoid repeated API calls.
        """
        try:
            if cached := _get_cached_cluster_name(connection_id):
                return cached

            # perform_request is already instrumented; the span_name == "elasticsearch"
            # guard inside it prevents recursive tracing of this info() call.
            if hasattr(instance, "info"):
                try:
                    if cluster_name := _extract_cluster_name_from_response(
                        instance.info()
                    ):
                        _store_cluster_name(connection_id, cluster_name)
                        return cluster_name
                except Exception as e:
                    logger.debug(f"elasticsearch cluster name discovery failed: {e}")

        except Exception:
            logger.debug("discover_cluster_name error:", exc_info=True)

        return None

    def _set_connection_span_attributes(
        span: "InstanaSpan",
        host: Optional[str],
        port: Optional[int],
        cluster_name: Optional[str],
    ) -> None:
        """Set elasticsearch connection-related span attributes."""
        if host:
            span.set_attribute("elasticsearch.address", host)
        if port is not None:
            span.set_attribute("elasticsearch.port", port)
        if cluster_name:
            span.set_attribute("elasticsearch.cluster", cluster_name)

    def _resolve_transport_host_port(
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
    ) -> tuple[Optional[str], Optional[int]]:
        """Read host and port from the first node in the transport node pool."""
        if hasattr(instance, "transport"):
            transport = instance.transport
            if hasattr(transport, "node_pool"):
                try:
                    nodes = list(transport.node_pool.all())
                    if nodes:
                        cfg = nodes[0].config
                        return cfg.host, cfg.port
                except Exception:
                    pass
        return None, None

    def collect_connection_info(
        span: "InstanaSpan",
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
    ) -> None:
        """
        Collect connection information and cluster name (sync).
        Uses caching to optimize performance.
        """
        try:
            if not (connection_id := get_connection_id(instance)):
                return

            cached = _connection_cache[connection_id]
            if cached.get("host"):
                _set_connection_span_attributes(
                    span,
                    cached.get("host"),
                    cached.get("port"),
                    cached.get("cluster_name"),
                )
                # No fallback to host:port — backend uses address+port when cluster is absent
                return

            host, port = _resolve_transport_host_port(instance)
            if host is not None:
                cached.update({"host": host, "port": port, "last_updated": time.time()})
                _set_connection_span_attributes(
                    span, host, port, discover_cluster_name(instance, connection_id)
                )
                # No fallback to host:port — backend uses address+port when cluster is absent

        except Exception:
            logger.debug("elasticsearch collect_connection_info error:", exc_info=True)

    def shorten_query_string(query: str, max_length: int = 1000) -> str:
        """
        Shorten long query strings for logging
        """
        if not query or len(query) <= max_length:
            return query
        return query[:max_length] + "..."

    def to_string_es_multi_parameter(
        param: Optional[Union[str, list[str]]],
    ) -> Optional[str]:
        """
        Convert Elasticsearch multi-parameter to string
        Handles: string, list, None
        """
        if param is None:
            return None
        if isinstance(param, str):
            return "_all" if param == "" else param
        if isinstance(param, list):
            return ",".join(str(p) for p in param)
        return str(param)

    def extract_index_from_url(url: str) -> Optional[str]:
        """Extract index name from URL path"""
        try:
            # Match pattern: /index_name/...
            if match := INDEX_PATTERN.match(url):
                index = match.group(1)
                # Filter out special endpoints
                if not index.startswith("_"):
                    return index
        except Exception:
            logger.debug("extract_index_from_url error:", exc_info=True)
        return None

    def extract_document_id_from_url(url: str) -> Optional[str]:
        """
        Extract document ID from URL
        Pattern: /index/_doc/document_id
        """
        try:
            if match := DOCUMENT_ID_PATTERN.match(url):
                return match.group(1)
        except Exception:
            logger.debug("extract_document_id_from_url error:", exc_info=True)
        return None

    def detect_action_from_url(method: str, url: str) -> str:
        """
        Detect Elasticsearch action from HTTP method and URL.
        Returns action name like: search, index, get, delete, bulk, etc.

        Looks for the first ``_keyword`` segment in the URL path and resolves
        it via lookup tables, falling back to the HTTP method when nothing
        matches.
        """
        try:
            url_lower = url.lower()

            # Find the first _keyword segment in the URL (e.g. /_search, /_bulk)
            for segment in url_lower.split("/"):
                if not segment.startswith("_"):
                    continue
                # Strip query-string from segment
                keyword = segment.split("?")[0]
                # Method-specific lookup takes priority
                if keyword in _URL_KEYWORD_METHOD_ACTION:
                    action = _URL_KEYWORD_METHOD_ACTION[keyword].get(method)
                    if action:
                        return action
                # Generic keyword lookup
                if keyword in _URL_KEYWORD_ACTION:
                    return _URL_KEYWORD_ACTION[keyword]

            # Fallback to HTTP method
            return method.lower()
        except Exception:
            logger.debug("detect_action_from_url error:", exc_info=True)
            return method.lower()

    def _process_multi_operation(
        span: "InstanaSpan",
        action: str,
        body: Optional[Union[dict[str, Any], str]],
        params: Optional[dict[str, Any]],
    ) -> bool:
        """Handle Elasticsearch multi-operation actions."""
        if action == "mget":
            process_mget_params(span, body, params)
            return True
        if action == "msearch":
            process_msearch_params(span, body)
            return True
        if action == "bulk":
            process_bulk_params(span, body)
            return True
        return False

    def _extract_query_string(body: Union[dict[str, Any], str]) -> str:
        """Convert a request body to a query string."""
        if isinstance(body, dict):
            return json.dumps(body)
        if isinstance(body, str):
            return body
        return str(body)

    def _set_search_query_attribute(
        span: "InstanaSpan", body: Union[dict[str, Any], str]
    ) -> None:
        """Set the search query span attribute when possible."""
        try:
            query_str = _extract_query_string(body)
            span.set_attribute("elasticsearch.query", shorten_query_string(query_str))
        except Exception:
            logger.debug("extract query error:", exc_info=True)

    def _set_request_param_attributes(
        span: "InstanaSpan",
        params: Optional[dict[str, Any]],
        index: Optional[str],
        doc_id: Optional[str],
    ) -> None:
        """Set span attributes derived from request params."""
        if not params:
            return
        if not index and "index" in params:
            index_param = to_string_es_multi_parameter(params.get("index"))
            if index_param:
                span.set_attribute(ELASTICSEARCH_INDEX_ATTRIBUTE, index_param)
        if not doc_id and "id" in params:
            span.set_attribute(ELASTICSEARCH_ID_ATTRIBUTE, str(params["id"]))

    def extract_params_from_request(
        span: "InstanaSpan",
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[Union[dict[str, Any], str]] = None,
    ) -> None:
        """
        Extract and set Elasticsearch parameters from request
        Handles: index, type, id, query extraction, multi-operations
        """
        try:
            action = detect_action_from_url(method, url)
            span.set_attribute("elasticsearch.action", action)

            if _process_multi_operation(span, action, body, params):
                return

            index = extract_index_from_url(url)
            if index:
                span.set_attribute(ELASTICSEARCH_INDEX_ATTRIBUTE, index)

            doc_id = extract_document_id_from_url(url)
            if doc_id:
                span.set_attribute(ELASTICSEARCH_ID_ATTRIBUTE, doc_id)

            if action == "search" and body:
                _set_search_query_attribute(span, body)

            _set_request_param_attributes(span, params, index, doc_id)

        except Exception:
            logger.debug("extract_params_from_request error:", exc_info=True)

    def _collect_mget_body_fields(
        body: dict[str, Any],
    ) -> tuple[set, list]:
        """Extract indices and doc_ids from an mget request body."""
        indices: set = set()
        doc_ids: list = []
        docs = body.get("docs", [])
        if isinstance(docs, list):
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                if "_index" in doc:
                    indices.add(doc["_index"])
                if "_id" in doc:
                    doc_ids.append(str(doc["_id"]))
        ids = body.get("ids", [])
        if isinstance(ids, list) and ids:
            doc_ids.extend(str(id_val) for id_val in ids)
        return indices, doc_ids

    def _format_doc_ids(doc_ids: list) -> str:
        """Format a list of doc IDs into a bounded span attribute string."""
        ids_str = ",".join(doc_ids[:10])
        if len(doc_ids) > 10:
            ids_str += f",... ({len(doc_ids)} total)"
        return ids_str

    def process_mget_params(
        span: "InstanaSpan",
        body: Optional[Union[dict[str, Any], str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Process multi-get (mget) parameters
        Extracts index and id from docs array or ids array.
        """
        try:
            indices: set = set()
            doc_ids: list = []

            if body and isinstance(body, dict):
                indices, doc_ids = _collect_mget_body_fields(body)

            if params and "index" in params and not indices:
                index_param = to_string_es_multi_parameter(params.get("index"))
                if index_param:
                    indices.add(index_param)

            if indices:
                span.set_attribute(
                    ELASTICSEARCH_INDEX_ATTRIBUTE, ",".join(sorted(indices))
                )
            if doc_ids:
                span.set_attribute(ELASTICSEARCH_ID_ATTRIBUTE, _format_doc_ids(doc_ids))

        except Exception:
            logger.debug("process_mget_params error:", exc_info=True)

    def _parse_ndjson_body(body: Union[str, list[Any]]) -> Optional[list]:
        """
        Normalise a bulk/msearch body into a list of dicts.
        Accepts a newline-delimited JSON string or an already-parsed list.
        Returns None when the body type is unsupported.
        """
        if isinstance(body, str):
            result = []
            for line in body.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return result
        if isinstance(body, list):
            return body
        return None

    def _collect_msearch_pair(
        body_list: list,
        i: int,
        indices: set,
        queries: list,
    ) -> None:
        """Process one header+body pair from an msearch body list."""
        if i < len(body_list) and isinstance(body_list[i], dict):
            header = body_list[i]
            index_val = to_string_es_multi_parameter(header.get("index"))
            if index_val:
                indices.add(index_val)
        if i + 1 < len(body_list) and isinstance(body_list[i + 1], dict):
            query_body = body_list[i + 1]
            if query_body:
                queries.append(query_body)

    def _set_msearch_query_attribute(span: "InstanaSpan", queries: list) -> None:
        """Serialise and set the combined msearch query span attribute."""
        try:
            combined_query = json.dumps({"queries": queries})
            span.set_attribute(
                "elasticsearch.query",
                shorten_query_string(combined_query, max_length=1000),
            )
        except Exception:
            logger.debug("msearch query serialization error:", exc_info=True)

    def process_msearch_params(
        span: "InstanaSpan",
        body: Optional[Union[dict[str, Any], str]] = None,
    ) -> None:
        """
        Process multi-search (msearch) parameters
        Extracts indices and queries from body array
        Body format: [header, body, header, body, ...]
        """
        try:
            indices: set = set()
            queries: list = []

            if body:
                body_list = _parse_ndjson_body(body)
                if body_list is None:
                    return
                for i in range(0, len(body_list), 2):
                    _collect_msearch_pair(body_list, i, indices, queries)

            if indices:
                span.set_attribute(
                    ELASTICSEARCH_INDEX_ATTRIBUTE, ",".join(sorted(indices))
                )
            if queries:
                _set_msearch_query_attribute(span, queries)

        except Exception:
            logger.debug("process_msearch_params error:", exc_info=True)

    _BULK_OP_TYPES = ("index", "create", "update", "delete")

    def _process_bulk_action_line(
        action_line: dict,
        indices: set,
        operations: set,
    ) -> None:
        """Extract operation type and index from a single bulk action line."""
        for op_type in _BULK_OP_TYPES:
            if op_type in action_line:
                operations.add(op_type)
                op_data = action_line[op_type]
                if isinstance(op_data, dict) and "_index" in op_data:
                    indices.add(op_data["_index"])
                break

    def process_bulk_params(
        span: "InstanaSpan",
        body: Optional[Union[dict[str, Any], str]] = None,
    ) -> None:
        """
        Process bulk operation parameters
        Extracts operation count and indices
        Body format: [action, doc, action, doc, ...]
        """
        try:
            indices: set = set()
            operation_count = 0
            operations: set = set()

            if body:
                body_list = _parse_ndjson_body(body)
                if body_list is None:
                    return
                for i in range(0, len(body_list), 2):
                    if i < len(body_list) and isinstance(body_list[i], dict):
                        operation_count += 1
                        _process_bulk_action_line(body_list[i], indices, operations)

            if indices:
                span.set_attribute(
                    ELASTICSEARCH_INDEX_ATTRIBUTE, ",".join(sorted(indices))
                )
            if operation_count > 0:
                span.set_attribute("elasticsearch.bulk.size", operation_count)
            if operations:
                span.set_attribute(
                    "elasticsearch.bulk.operations", ",".join(sorted(operations))
                )

        except Exception:
            logger.debug("process_bulk_params error:", exc_info=True)

    def _count_hits_total(total: Union[int, dict[str, Any]]) -> int:
        """Return the numeric hit count from an ES hits.total value."""
        if isinstance(total, int):
            return total
        if isinstance(total, dict):
            return total.get("value", 0)
        return 0

    def _handle_search_hits(span: "InstanaSpan", body: dict[str, Any]) -> None:
        """Set the hits attribute for a standard search response."""
        hits = body.get("hits", {})
        if "total" in hits:
            span.set_attribute(
                ELASTICSEARCH_HITS_ATTRIBUTE, _count_hits_total(hits["total"])
            )

    def _handle_msearch_response(span: "InstanaSpan", body: dict[str, Any]) -> None:
        """Set span attributes for an msearch response."""
        total_hits = 0
        success_count = 0
        error_count = 0
        for resp in body["responses"]:
            if not isinstance(resp, dict):
                continue
            if "error" in resp:
                error_count += 1
            else:
                success_count += 1
                hits = resp.get("hits", {})
                if "total" in hits:
                    total_hits += _count_hits_total(hits["total"])
        span.set_attribute(ELASTICSEARCH_HITS_ATTRIBUTE, total_hits)
        if success_count > 0:
            span.set_attribute("elasticsearch.msearch.success", success_count)
        if error_count > 0:
            span.set_attribute("elasticsearch.msearch.errors", error_count)

    def _handle_mget_response(span: "InstanaSpan", body: dict[str, Any]) -> None:
        """Set span attributes for an mget response."""
        found_count = sum(
            1
            for doc in body["docs"]
            if isinstance(doc, dict) and doc.get("found", False)
        )
        not_found_count = sum(
            1
            for doc in body["docs"]
            if isinstance(doc, dict) and not doc.get("found", False)
        )
        if found_count > 0:
            span.set_attribute("elasticsearch.mget.found", found_count)
        if not_found_count > 0:
            span.set_attribute("elasticsearch.mget.not_found", not_found_count)

    def _handle_bulk_response(span: "InstanaSpan", body: dict[str, Any]) -> None:
        """Set span attributes for a bulk response."""
        success_count = 0
        error_count = 0
        for item in body["items"]:
            if not isinstance(item, dict):
                continue
            for op_result in item.values():
                if isinstance(op_result, dict):
                    if 200 <= op_result.get("status", 0) < 300:
                        success_count += 1
                    else:
                        error_count += 1
        if success_count > 0:
            span.set_attribute("elasticsearch.bulk.success", success_count)
        if error_count > 0:
            span.set_attribute("elasticsearch.bulk.errors", error_count)

    def extract_response_metadata(
        span: "InstanaSpan", response: "ObjectApiResponse[Any]"
    ) -> None:
        """
        Extract metadata from Elasticsearch response
        Handles: hits count, connection details, multi-operation responses
        """
        try:
            if not (hasattr(response, "body") and isinstance(response.body, dict)):
                return
            body = response.body
            if "hits" in body:
                _handle_search_hits(span, body)
            elif "responses" in body and isinstance(body["responses"], list):
                _handle_msearch_response(span, body)
            elif "docs" in body and isinstance(body["docs"], list):
                _handle_mget_response(span, body)
            elif "items" in body and isinstance(body["items"], list):
                _handle_bulk_response(span, body)
        except Exception:
            logger.debug("extract_response_metadata error:", exc_info=True)

    # Standard (Sync) Client Instrumentation
    # ES 8.x/9.x: perform_request(method, path, *, params, headers, body, endpoint_id, path_parts)
    # All parameters after `path` are keyword-only; we must forward them faithfully so the
    # internal mimetype-compatibility header rewriting (_COMPAT_MIMETYPE_RE) still runs.
    @wrapt.patch_function_wrapper(
        "elasticsearch._sync.client._base", "BaseClient.perform_request"
    )
    def perform_request_with_instana(
        wrapped: Callable[..., Any],
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        tracer, _, span_name = get_tracer_tuple()
        if span_name == "elasticsearch":
            return wrapped(*args, **kwargs)
        if not tracer:
            logger.debug(
                "elasticsearch: tracer not available, skipping instrumentation"
            )
            return wrapped(*args, **kwargs)

        parent_context = get_current()

        logger.debug("elasticsearch: creating span for request")

        # ES uses keyword-only parameters after `path`.
        # Extract method and path from positional args or kwargs.
        method = args[0] if len(args) > 0 else kwargs.get("method", "GET")
        # ES uses `path`; older versions used `url` as positional arg[1]
        url = args[1] if len(args) > 1 else kwargs.get("path", kwargs.get("url", "/"))
        params = kwargs.get("params")
        body = kwargs.get("body")

        with tracer.start_as_current_span(
            "elasticsearch", context=parent_context
        ) as span:
            try:
                logger.debug(f"elasticsearch: method={method}, url={url}")

                # Collect connection info first
                collect_connection_info(span, instance)

                # Extract parameters and set attributes
                extract_params_from_request(span, method, url, params, body)

                # Set URL as endpoint (backend fallback label when action is absent)
                span.set_attribute("elasticsearch.endpoint", url)
                span.set_attribute("elasticsearch.url", url)

                # Execute the request — forward all original args/kwargs unchanged
                # so ES internal header processing (mimetype compat) still works
                response = wrapped(*args, **kwargs)

                # Extract response metadata
                extract_response_metadata(span, response)

                if (
                    hasattr(response, "meta")
                    and hasattr(response.meta, "status")
                    and response.meta.status >= 500
                ):
                    span.set_attribute(
                        ELASTICSEARCH_ERROR_ATTRIBUTE, f"HTTP {response.meta.status}"
                    )

                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute(ELASTICSEARCH_ERROR_ATTRIBUTE, str(exc))
                raise

    # ---------------------------------------------------------------------------
    # Async Client Instrumentation
    # ---------------------------------------------------------------------------

    async def _async_discover_cluster_name(
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
        connection_id: str,
    ) -> Optional[str]:
        """
        Async version of discover_cluster_name.
        Reuses the shared cache helpers; only the instance.info() call is awaited.
        """
        try:
            if cached := _get_cached_cluster_name(connection_id):
                return cached

            if hasattr(instance, "info"):
                try:
                    cluster_name = _extract_cluster_name_from_response(
                        await instance.info()
                    )
                    if cluster_name:
                        _store_cluster_name(connection_id, cluster_name)
                        return cluster_name
                except Exception as e:
                    logger.debug(
                        f"elasticsearch async cluster name discovery failed: {e}"
                    )

        except Exception:
            logger.debug("_async_discover_cluster_name error:", exc_info=True)

        return None

    async def _async_collect_connection_info(
        span: "InstanaSpan",
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
    ) -> None:
        """
        Async version of collect_connection_info.
        Reuses shared helpers; only cluster discovery is awaited.
        """
        try:
            if not (connection_id := get_connection_id(instance)):
                return

            cached = _connection_cache[connection_id]
            if cached.get("host"):
                _set_connection_span_attributes(
                    span,
                    cached.get("host"),
                    cached.get("port"),
                    cached.get("cluster_name"),
                )
                return

            host, port = _resolve_transport_host_port(instance)
            if host is not None:
                cached.update({"host": host, "port": port, "last_updated": time.time()})
                _set_connection_span_attributes(
                    span,
                    host,
                    port,
                    await _async_discover_cluster_name(instance, connection_id),
                )

        except Exception:
            logger.debug(
                "elasticsearch async collect_connection_info error:", exc_info=True
            )

    @wrapt.patch_function_wrapper(
        "elasticsearch._async.client._base", "BaseClient.perform_request"
    )
    async def async_perform_request_with_instana(
        wrapped: Callable[..., Coroutine[Any, Any, Any]],
        instance: "Union[Elasticsearch, AsyncElasticsearch]",
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        tracer, _, span_name = get_tracer_tuple()
        if span_name == "elasticsearch":
            return await wrapped(*args, **kwargs)

        if not tracer:
            logger.debug(
                "elasticsearch async: tracer not available, skipping instrumentation"
            )
            return await wrapped(*args, **kwargs)

        parent_context = get_current()

        logger.debug("elasticsearch async: creating span for request")

        method = args[0] if len(args) > 0 else kwargs.get("method", "GET")
        url = args[1] if len(args) > 1 else kwargs.get("path", kwargs.get("url", "/"))
        params = kwargs.get("params")
        body = kwargs.get("body")

        with tracer.start_as_current_span(
            "elasticsearch", context=parent_context
        ) as span:
            try:
                logger.debug(f"elasticsearch async: method={method}, url={url}")

                await _async_collect_connection_info(span, instance)

                extract_params_from_request(span, method, url, params, body)

                span.set_attribute("elasticsearch.endpoint", url)
                span.set_attribute("elasticsearch.url", url)

                response = await wrapped(*args, **kwargs)

                extract_response_metadata(span, response)

                if (
                    hasattr(response, "meta")
                    and hasattr(response.meta, "status")
                    and response.meta.status >= 500
                ):
                    span.set_attribute(
                        ELASTICSEARCH_ERROR_ATTRIBUTE, f"HTTP {response.meta.status}"
                    )

                return response
            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute(ELASTICSEARCH_ERROR_ATTRIBUTE, str(exc))
                raise

    logger.debug("Instrumenting elasticsearch")

except ImportError:
    pass

# Made with Bob
