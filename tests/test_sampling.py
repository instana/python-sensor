# (c) Copyright IBM Corp. 2024

from typing import Generator

import pytest

from instana.sampling import InstanaSampler, SamplingPolicy


class TestInstanaSampler:
    @pytest.fixture(autouse=True)
    def _resource(self) -> Generator[None, None, None]:
        self.sampler = InstanaSampler()
        yield
        self.sampler = None

    def test_sampling_policy(self) -> None:
        assert self.sampler._sampled == SamplingPolicy.DROP
        assert self.sampler._sampled.name == "DROP"
        assert self.sampler._sampled.value == 0

    def test_sampler(self) -> None:
        assert not self.sampler.sampled()
