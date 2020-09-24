from __future__ import absolute_import

from instana.util import validate_url


def setup_method():
    pass


def test_validate_url():
    assert(validate_url("http://localhost:3000"))
    assert(validate_url("http://localhost:3000/"))
    assert(validate_url("https://localhost:3000/path/item"))
    assert(validate_url("http://localhost"))
    assert(validate_url("https://localhost/"))
    assert(validate_url("https://localhost/path/item"))
    assert(validate_url("http://127.0.0.1"))
    assert(validate_url("https://10.0.12.221/"))
    assert(validate_url("http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/"))
    assert(validate_url("https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443/"))
    assert(validate_url("boligrafo") is False)
    assert(validate_url("http:boligrafo") is False)
    assert(validate_url(None) is False)

class _TraceContextMixin:
    def assertTraceContextPropagated(self, parent_span, child_span):
        self.assertEqual(parent_span.t, child_span.t)
        self.assertEqual(parent_span.s, child_span.p)
        self.assertNotEqual(parent_span.s, child_span.s)
