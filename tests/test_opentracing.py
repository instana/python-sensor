from opentracing.harness.api_check import APICompatibilityCheckMixin
from instana.tracer import InstanaTracer
from nose.plugins.skip import SkipTest


class TestInstanaTracer(InstanaTracer, APICompatibilityCheckMixin):
    def tracer(self):
        return self

    def test_binary_propagation(self):
        raise SkipTest('Binary format is not supported')

    def test_mandatory_formats(self):
        raise SkipTest('Binary format is not supported')
