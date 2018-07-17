from nose.plugins.skip import SkipTest
from opentracing.harness.api_check import APICompatibilityCheckMixin

from instana.tracer import InstanaTracer


class TestInstanaTracer(InstanaTracer, APICompatibilityCheckMixin):
    def tracer(self):
        return self

    def test_binary_propagation(self):
        raise SkipTest('Binary format is not supported')

    def test_mandatory_formats(self):
        raise SkipTest('Binary format is not supported')

    def check_baggage_values(self):
        return True

    def is_parent(self, parent, span):
        # use `Span` ids to check parenting
        if parent is None:
            return span.parent_id is None

        return parent.context.span_id == span.parent_id
