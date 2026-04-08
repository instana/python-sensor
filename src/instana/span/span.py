# (c) Copyright IBM Corp. 2021, 2025
# (c) Copyright Instana Inc. 2017

"""
This module contains the classes that represents spans.

InstanaSpan - the OpenTelemetry based span used during tracing

When an InstanaSpan is finished, it is converted into either an SDKSpan
or RegisteredSpan depending on type.

BaseSpan: Base class containing the commonalities for the two descendants
  - SDKSpan: Class that represents an SDK type span
  - RegisteredSpan: Class that represents a Registered type span
"""

from threading import Lock
from time import time_ns
from typing import Dict, Optional, Sequence, Union

from opentelemetry.context import get_value
from opentelemetry.context.context import Context
from opentelemetry.trace import (
    _SPAN_KEY,
    DEFAULT_TRACE_OPTIONS,
    DEFAULT_TRACE_STATE,
    INVALID_SPAN_ID,
    INVALID_TRACE_ID,
    Span,
    SpanKind,
)
from opentelemetry.trace.span import NonRecordingSpan
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.util import types

from instana.log import logger
from instana.recorder import StanRecorder
from instana.span.kind import HTTP_SPANS
from instana.span.readable_span import Event, ReadableSpan
from instana.span.stack_trace import add_stack_trace_if_needed
from instana.span_context import SpanContext


class InstanaSpan(Span, ReadableSpan):
    def __init__(
        self,
        name: str,
        context: SpanContext,
        span_processor: StanRecorder,
        parent_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        attributes: types.Attributes = {},
        events: Sequence[Event] = [],
        status: Optional[Status] = Status(StatusCode.UNSET),
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> None:
        super().__init__(
            name=name,
            context=context,
            parent_id=parent_id,
            start_time=start_time,
            end_time=end_time,
            attributes=attributes,
            events=events,
            status=status,
            kind=kind,
        )
        self._span_processor = span_processor
        self._lock = Lock()

    def get_span_context(self) -> SpanContext:
        return self._context

    def set_attributes(self, attributes: Dict[str, types.AttributeValue]) -> None:
        if not self._attributes:
            self._attributes = {}

        with self._lock:
            for key, value in attributes.items():
                self._attributes[key] = value

    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        return self.set_attributes({key: value})

    def update_name(self, name: str) -> None:
        with self._lock:
            self._name = name

    def is_recording(self) -> bool:
        return self._end_time is None

    def set_status(
        self,
        status: Union[Status, StatusCode],
        description: Optional[str] = None,
    ) -> None:
        # Ignore future calls if status is already set to OK
        # Ignore calls to set to StatusCode.UNSET
        if isinstance(status, Status):
            if (
                self._status
                and self._status.status_code is StatusCode.OK
                or status.status_code is StatusCode.UNSET
            ):
                return
            if description is not None:
                logger.warning(
                    "Description %s ignored. Use either `Status` or `(StatusCode, Description)`",
                    description,
                )
            self._status = status
        elif isinstance(status, StatusCode):
            if (
                self._status
                and self._status.status_code is StatusCode.OK
                or status is StatusCode.UNSET
            ):
                return
            self._status = Status(status, description)

    def add_event(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
    ) -> None:
        event = Event(
            name=name,
            attributes=attributes,
            timestamp=timestamp,
        )

        self._events.append(event)

    def record_exception(
        self,
        exception: Exception,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
        escaped: bool = False,
    ) -> None:
        """
        Records an exception as a span event. This will record pertinent info from the exception and
        assure that this span is marked as errored.
        """
        try:
            message = ""
            self.mark_as_errored()
            if hasattr(exception, "__str__") and len(str(exception)) > 0:
                message = str(exception)
            elif hasattr(exception, "message") and exception.message is not None:
                message = exception.message
            else:
                message = repr(exception)

            if self.name in ["rpc-server", "rpc-client"]:
                self.set_attribute("rpc.error", message)
            elif self.name == "mysql":
                self.set_attribute("mysql.error", message)
            elif self.name == "postgres":
                self.set_attribute("pg.error", message)
            elif self.name in HTTP_SPANS:
                self.set_attribute("http.error", message)
            elif self.name in ["celery-client", "celery-worker"]:
                self.set_attribute("error", message)
            elif self.name == "sqlalchemy":
                self.set_attribute("sqlalchemy.err", message)
            elif self.name == "aws.lambda.entry":
                self.set_attribute("lambda.error", message)
            elif self.name.startswith("kafka"):
                self.set_attribute("kafka.error", message)
            else:
                _attributes = {"message": message}
                if attributes:
                    _attributes.update(attributes)
                self.add_event(
                    name="exception", attributes=_attributes, timestamp=timestamp
                )
        except Exception:
            logger.debug("span.record_exception", exc_info=True)
            raise

    def _readable_span(self) -> ReadableSpan:
        return ReadableSpan(
            name=self.name,
            context=self.context,
            parent_id=self.parent_id,
            start_time=self.start_time,
            end_time=self.end_time,
            attributes=self.attributes,
            events=self.events,
            status=self.status,
            stack=self.stack,
            kind=self.kind,
        )

    def end(self, end_time: Optional[int] = None) -> None:
        with self._lock:
            self._end_time = end_time if end_time else time_ns()
            self._duration = self._end_time - self._start_time

        # add_stack_trace_if_needed(self)

        from instana.singletons import get_agent
        agent = get_agent()
        
        # Record span to Instana backend (unless export_mode is "otlp")
        export_mode = getattr(agent.options, 'export_mode', 'instana')
        if export_mode != "otlp":
            self._span_processor.record_span(self._readable_span())

        # Export to OTLP if enabled
        try:
            
            if hasattr(agent, 'options') and hasattr(agent.options, 'otlp_enabled'):                
                if export_mode in ['otlp', 'both'] and agent.options.otlp_enabled:
                    # Skip OTLP export for spans that are OTLP export requests themselves
                    # This prevents infinite recursion when the OTLP exporter makes HTTP requests
                    otlp_endpoint = getattr(agent.options, 'otlp_endpoint', '')
                    span_url = self._attributes.get('http.url', '') if self._attributes else ''
                    
                    # Check if this span is an OTLP export request
                    is_otlp_export_span = (
                        otlp_endpoint and span_url and
                        (otlp_endpoint in span_url or '/v1/traces' in span_url)
                    )
                    
                    if not is_otlp_export_span:
                        from instana.singletons import provider
                        
                        if hasattr(provider, '_otlp_processor'):
                            from instana.span.otlp_span_adapter import OTLPSpanAdapter
                            
                            # Convert InstanaSpan to OTel ReadableSpan format
                            otlp_span = OTLPSpanAdapter(self)
                            
                            # Send to OTLP processor for batching and export
                            provider._otlp_processor.on_end(otlp_span)

                            # Direct export for immediate visibility (bypasses batching)
                            # This ensures spans appear immediately in the backend
                            processor = provider._otlp_processor
                            exporter = processor.span_exporter

                            from opentelemetry.sdk.trace.export import SpanExportResult
                            result = exporter.export((otlp_span,))
                            
                            if result == SpanExportResult.SUCCESS:
                                logger.debug(f"OTLP export succeeded: {self.name}")
                                # Convert trace_id to hex for logging
                                trace_id_hex = format(otlp_span.get_span_context().trace_id, '032x')
                                logger.debug(
                                    f"Span exported to OTLP: {self.name} "
                                    f"(trace_id={trace_id_hex})"
                                )
                            else:
                                logger.debug(f"OTLP export failed: {self.name}, result={result}")
                    else:
                        logger.debug(
                            f"Skipping OTLP export for OTLP exporter request: {self.name}"
                        )
                        
        except Exception as e:
            logger.debug(f"Failed to export span to OTLP: {e}", exc_info=True)

    def mark_as_errored(self, attributes: types.Attributes = None) -> None:
        """
        Mark this span as errored.

        @param attributes: optional attributes to add to the span
        """
        try:
            ec = self.attributes.get("ec", 0)
            self.set_attribute("ec", ec + 1)

            if attributes is not None and isinstance(attributes, dict):
                for key in attributes:
                    self.set_attribute(key, attributes[key])
        except Exception:
            logger.debug("span.mark_as_errored", exc_info=True)

    def assure_errored(self) -> None:
        """
        Make sure that this span is marked as errored.
        @return: None
        """
        try:
            ec = self.attributes.get("ec", None)
            if ec is None or ec == 0:
                self.set_attribute("ec", 1)
        except Exception:
            logger.debug("span.assure_errored", exc_info=True)


INVALID_SPAN_CONTEXT = SpanContext(
    trace_id=INVALID_TRACE_ID,
    span_id=INVALID_SPAN_ID,
    is_remote=False,
    trace_flags=DEFAULT_TRACE_OPTIONS,
    trace_state=DEFAULT_TRACE_STATE,
)
INVALID_SPAN = NonRecordingSpan(INVALID_SPAN_CONTEXT)


def get_current_span(context: Optional[Context] = None) -> Union[InstanaSpan, Span]:
    """Retrieve the current span.

    Args:
        context: A Context object. If one is not passed, the
            default current context is used instead.

    Returns:
        The Span set in the context if it exists. INVALID_SPAN otherwise.
    """
    span = get_value(_SPAN_KEY, context=context)
    if span is None or not isinstance(span, (InstanaSpan, Span)):
        return INVALID_SPAN
    return span
