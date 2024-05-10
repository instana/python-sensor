# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

class _TraceContextMixin:
    def assertTraceContextPropagated(self, parent_span, child_span):
        self.assertEqual(parent_span.t, child_span.t)
        self.assertEqual(parent_span.s, child_span.p)
        self.assertNotEqual(parent_span.s, child_span.s)

    def assertErrorLogging(self, spans):
        for span in spans:
            self.assertIsNone(span.ec)
