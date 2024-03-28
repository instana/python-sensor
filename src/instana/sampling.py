# (c) Copyright IBM Corp. 2024

import abc
import enum


class SamplingPolicy(enum.Enum):
    # IsRecording() == False
    # Span will not be recorded and all events and attributes will be dropped.
    # https://opentelemetry.io/docs/specs/otel/trace/api/#isrecording
    DROP = 0
    # IsRecording() == True, but Sampled flag MUST NOT be set.
    RECORD_ONLY = 1
    # IsRecording() == True AND Sampled flag MUST be set.
    RECORD_AND_SAMPLE = 2


class Sampler(abc.ABC):
    """Samplers choose whether the span is recorded or dropped.

    A variety of sampling algorithms are available, and choosing which sampler
    to use and how to configure it is one of the most confusing parts of
    setting up a tracing system.
    """

    @abc.abstractmethod
    def sampled(self) -> bool:
        """
        Returns if a span was dropped (False) or recorded (True).

        Calling a span “sampled” can mean it was “sampled out” (dropped)
        or “sampled in” (recorded).
        """
        pass


class InstanaSampler(Sampler):
    def __init__(self) -> None:
        # Instana never samples.
        self._sampled: SamplingPolicy = SamplingPolicy.DROP

    def sampled(self) -> bool:
        return False if self._sampled == SamplingPolicy.DROP else True
