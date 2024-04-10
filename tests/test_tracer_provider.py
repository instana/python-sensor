# (c) Copyright IBM Corp. 2024

from opentelemetry.trace.span import _SPAN_ID_MAX_VALUE, INVALID_SPAN_ID
from pytest import LogCaptureFixture

from instana.agent.host import HostAgent
from instana.agent.test import TestAgent
from instana.propagators.binary_propagator import BinaryPropagator
from instana.propagators.format import Format
from instana.propagators.http_propagator import HTTPPropagator
from instana.propagators.text_propagator import TextPropagator
from instana.recorder import StanRecorder
from instana.sampling import InstanaSampler
from instana.tracer import InstanaTracer, InstanaTracerProvider


def test_tracer_provider_defaults() -> None:
    provider = InstanaTracerProvider()
    assert isinstance(provider.sampler, InstanaSampler)
    assert isinstance(provider.recorder, StanRecorder)
    assert isinstance(provider._span_processor, HostAgent)
    assert len(provider._propagators) == 3
    assert isinstance(provider._propagators[Format.HTTP_HEADERS], HTTPPropagator)
    assert isinstance(provider._propagators[Format.TEXT_MAP], TextPropagator)
    assert isinstance(provider._propagators[Format.BINARY], BinaryPropagator)


def test_tracer_provider_get_tracer() -> None:
    provider = InstanaTracerProvider()
    tracer = provider.get_tracer("instana.test.tracer")

    assert isinstance(tracer, InstanaTracer)
    assert tracer.tracer_id > INVALID_SPAN_ID
    assert tracer.tracer_id <= _SPAN_ID_MAX_VALUE


def test_tracer_provider_get_tracer_empty_instrumenting_module_name(
    caplog: LogCaptureFixture,
) -> None:
    provider = InstanaTracerProvider()
    tracer = provider.get_tracer("")

    assert "get_tracer called with missing module name." == caplog.record_tuples[0][2]
    assert isinstance(tracer, InstanaTracer)
    assert tracer.tracer_id > INVALID_SPAN_ID
    assert tracer.tracer_id <= _SPAN_ID_MAX_VALUE


def test_tracer_provider_add_span_processor() -> None:
    provider = InstanaTracerProvider()
    assert isinstance(provider._span_processor, HostAgent)

    provider.add_span_processor(TestAgent())
    assert isinstance(provider._span_processor, TestAgent)
