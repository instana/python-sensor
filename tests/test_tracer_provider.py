# (c) Copyright IBM Corp. 2024

from pytest import LogCaptureFixture

from instana.agent.base import BaseAgent
from instana.agent.host import HostAgent
from instana.propagators.binary_propagator import BinaryPropagator
from instana.propagators.format import Format
from instana.propagators.http_propagator import HTTPPropagator
from instana.propagators.kafka_propagator import KafkaPropagator
from instana.propagators.text_propagator import TextPropagator
from instana.recorder import StanRecorder
from instana.sampling import InstanaSampler
from instana.tracer import InstanaTracer, InstanaTracerProvider


def test_tracer_provider_defaults() -> None:
    provider = InstanaTracerProvider()
    assert isinstance(provider.sampler, InstanaSampler)
    assert isinstance(provider._span_processor, StanRecorder)
    assert isinstance(provider._exporter, HostAgent)
    assert len(provider._propagators) == 4
    assert isinstance(provider._propagators[Format.HTTP_HEADERS], HTTPPropagator)
    assert isinstance(provider._propagators[Format.TEXT_MAP], TextPropagator)
    assert isinstance(provider._propagators[Format.BINARY], BinaryPropagator)
    assert isinstance(provider._propagators[Format.KAFKA_HEADERS], KafkaPropagator)


def test_tracer_provider_get_tracer() -> None:
    provider = InstanaTracerProvider()
    tracer = provider.get_tracer("instana.test.tracer")

    assert isinstance(tracer, InstanaTracer)


def test_tracer_provider_get_tracer_empty_instrumenting_module_name(
    caplog: LogCaptureFixture,
) -> None:
    provider = InstanaTracerProvider()
    tracer = provider.get_tracer("")

    assert "get_tracer called with missing module name." in caplog.messages
    assert isinstance(tracer, InstanaTracer)


def test_tracer_provider_add_span_processor(span_processor: StanRecorder) -> None:
    provider = InstanaTracerProvider()
    assert isinstance(provider._span_processor, StanRecorder)
    assert isinstance(provider._span_processor.agent, HostAgent)
    assert provider._span_processor.THREAD_NAME == "InstanaSpan Recorder"

    provider.add_span_processor(span_processor)
    assert isinstance(provider._span_processor, StanRecorder)
    assert isinstance(provider._span_processor.agent, BaseAgent)
    assert provider._span_processor.THREAD_NAME == "InstanaSpan Recorder Test"
