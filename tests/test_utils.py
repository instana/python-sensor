# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

class _TraceContextMixin:
    def assertTraceContextPropagated(self, parent_span, child_span):
        assert parent_span.t == child_span.t
        assert parent_span.s == child_span.p
        assert parent_span.s != child_span.s

    def assertErrorLogging(self, spans):
        for span in spans:
            assert not span.ec
