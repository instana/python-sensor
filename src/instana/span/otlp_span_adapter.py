# (c) Copyright IBM Corp. 2026

"""
Adapter to convert InstanaSpan to OpenTelemetry SDK ReadableSpan format.
This enables OTLP export of Instana spans.
"""

from typing import Optional, Sequence, Mapping

from opentelemetry.sdk.trace import ReadableSpan as OTelReadableSpan
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanContext as OTelSpanContext
from opentelemetry.trace import SpanKind, TraceFlags, TraceState
from opentelemetry.trace.status import Status
from opentelemetry.sdk.util.instrumentation import InstrumentationInfo
from opentelemetry.util import types

from instana.span.span import InstanaSpan


class InstrumentationScope:
    """
    Wrapper for InstrumentationInfo that adds the attributes property
    required by OTLP exporter.
    """
    def __init__(self, name: str, version: Optional[str] = None, schema_url: Optional[str] = None):
        self.name = name
        self.version = version
        self.schema_url = schema_url
        self.attributes = {}  # Required by OTLP exporter


class OTLPSpanAdapter(OTelReadableSpan):
    """
    Adapter that wraps an InstanaSpan and presents it as an OTel SDK ReadableSpan.
    This allows InstanaSpans to be exported via OTLP exporters.
    """
    
    def __init__(self, instana_span: InstanaSpan):
        self._instana_span = instana_span
        
        # Get service name from environment or use default
        import os
        service_name = os.environ.get('INSTANA_SERVICE_NAME', 'instana-python-tracer')
        self._resource = Resource.create({"service.name": service_name})
        
        # Create InstrumentationScope with attributes property
        # (OTLP exporter requires attributes property)
        self._instrumentation_info = InstrumentationScope(
            name="instana",
            version="3.12.0", # to be fetched from a variable
            schema_url=None
        )
    
    @property
    def name(self) -> str:
        return self._instana_span.name
    
    @property
    def context(self) -> OTelSpanContext:
        """Convert Instana SpanContext to OTel SpanContext"""
        instana_ctx = self._instana_span.get_span_context()
        
        # Convert hex string IDs to integers
        # Instana uses 64-bit (16 hex chars) trace IDs, but OTLP requires 128-bit (32 hex chars)
        # Pad the trace ID to 32 hex characters (128 bits) by adding zeros at the start
        if isinstance(instana_ctx.trace_id, str):
            trace_id_hex = instana_ctx.trace_id.zfill(32)  # Pad to 32 hex chars
            trace_id = int(trace_id_hex, 16)
        else:
            trace_id = instana_ctx.trace_id
        
        span_id = int(instana_ctx.span_id, 16) if isinstance(instana_ctx.span_id, str) else instana_ctx.span_id
        
        return OTelSpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=instana_ctx.is_remote,
            trace_flags=TraceFlags(instana_ctx.trace_flags),
            trace_state=TraceState()
        )
    
    def get_span_context(self) -> OTelSpanContext:
        """Get the span context"""
        return self.context
    
    @property
    def kind(self) -> SpanKind:
        return self._instana_span._kind
    
    @property
    def parent(self) -> Optional[OTelSpanContext]:
        """Get parent span context if available"""
        if self._instana_span.parent_id:
            # Get trace_id from current span (already padded to 128 bits)
            instana_ctx = self._instana_span.get_span_context()
            if isinstance(instana_ctx.trace_id, str):
                trace_id_hex = instana_ctx.trace_id.zfill(32)  # Pad to 32 hex chars
                trace_id = int(trace_id_hex, 16)
            else:
                trace_id = instana_ctx.trace_id
            
            parent_span_id = int(self._instana_span.parent_id, 16) if isinstance(self._instana_span.parent_id, str) else self._instana_span.parent_id
            
            return OTelSpanContext(
                trace_id=trace_id,
                span_id=parent_span_id,
                is_remote=False,
                trace_flags=TraceFlags.DEFAULT,
                trace_state=TraceState()
            )
        return None
    
    @property
    def start_time(self) -> Optional[int]:
        return self._instana_span._start_time
    
    @property
    def end_time(self) -> Optional[int]:
        return self._instana_span._end_time
    
    @property
    def status(self) -> Status:
        return self._instana_span._status
    
    @property
    def attributes(self) -> Mapping[str, types.AttributeValue]:
        """Get span attributes as a mapping"""
        return self._instana_span._attributes if self._instana_span._attributes else {}
    
    @property
    def events(self) -> Sequence:
        """Get span events"""
        # Convert Instana events to OTel events
        from opentelemetry.sdk.trace import Event as OTelEvent
        
        otel_events = []
        for event in self._instana_span._events:
            otel_event = OTelEvent(
                name=event.name,
                attributes=event.attributes if event.attributes else {},
                timestamp=event.timestamp
            )
            otel_events.append(otel_event)
        return otel_events
    
    @property
    def links(self) -> Sequence:
        """Get span links (Instana doesn't support links yet)"""
        return []
    
    @property
    def resource(self) -> Resource:
        """Get the resource associated with this span"""
        return self._resource
    
    @property
    def instrumentation_info(self) -> InstrumentationInfo:
        """Get instrumentation info"""
        return self._instrumentation_info
    
    @property
    def instrumentation_scope(self):
        """Get instrumentation scope (alias for instrumentation_info for newer OTel SDK)"""
        return self._instrumentation_info
    
    @property
    def dropped_attributes(self) -> int:
        """Number of dropped attributes"""
        return 0
    
    @property
    def dropped_events(self) -> int:
        """Number of dropped events"""
        return 0
    
    @property
    def dropped_links(self) -> int:
        """Number of dropped links"""
        return 0
    
    def is_recording(self) -> bool:
        """Check if span is recording (always False for ended spans)"""
        return False
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """Convert span to JSON (not used by OTLP exporter)"""
        import json
        return json.dumps({
            "name": self.name,
            "trace_id": format(self.context.trace_id, '032x'),
            "span_id": format(self.context.span_id, '016x'),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": dict(self.attributes),
        }, indent=indent)

# Made with Bob
