from nose.tools import assert_equals
from instana.helpers import eum_snippet, eum_test_snippet

# fake trace_id to test against
trace_id = "aMLx9G2GnnQ6QyMCLJLuCM8nw"
# fake api key to test against
eum_api_key = "FJB66VjwGgGQX6jiCpekoR4vf"

# fake meta key/values
meta1 = "Z7RmMKQAiyCLEAmseNy7e6Vm4"
meta2 = "Dp2bowfm6kJVD9CccmyBt4ePD"
meta3 = "N4poUwbNz98YcvWRAizy2phCo"


def test_vanilla_eum_snippet():
    eum_string = eum_snippet(trace_id=trace_id, eum_api_key=eum_api_key)
    assert type(eum_string) is str

    assert eum_string.find(trace_id) != -1
    assert eum_string.find(eum_api_key) != -1


def test_eum_snippet_with_meta():
    meta_kvs = {}
    meta_kvs['meta1'] = meta1
    meta_kvs['meta2'] = meta2
    meta_kvs['meta3'] = meta3

    eum_string = eum_snippet(trace_id=trace_id, eum_api_key=eum_api_key, meta=meta_kvs)
    assert type(eum_string) is str

    assert eum_string.find(trace_id) != -1
    assert eum_string.find(eum_api_key) != -1
    assert eum_string.find(meta1) != -1
    assert eum_string.find(meta2) != -1
    assert eum_string.find(meta3) != -1


def test_eum_snippet_error():
    meta_kvs = {}
    meta_kvs['meta1'] = meta1
    meta_kvs['meta2'] = meta2
    meta_kvs['meta3'] = meta3

    # No active span on tracer & no trace_id passed in.
    eum_string = eum_snippet(eum_api_key=eum_api_key, meta=meta_kvs)
    assert_equals('', eum_string)


def test_vanilla_eum_test_snippet():
    eum_string = eum_test_snippet(trace_id=trace_id, eum_api_key=eum_api_key)
    assert type(eum_string) is str

    assert eum_string.find(trace_id) != -1
    assert eum_string.find(eum_api_key) != -1
    assert eum_string.find('reportingUrl') != -1
    assert eum_string.find('//eum-test-fullstack-0-us-west-2.instana.io') != -1


def test_eum_test_snippet_with_meta():
    meta_kvs = {}
    meta_kvs['meta1'] = meta1
    meta_kvs['meta2'] = meta2
    meta_kvs['meta3'] = meta3

    eum_string = eum_test_snippet(trace_id=trace_id, eum_api_key=eum_api_key, meta=meta_kvs)
    assert type(eum_string) is str
    assert eum_string.find('reportingUrl') != -1
    assert eum_string.find('//eum-test-fullstack-0-us-west-2.instana.io') != -1

    assert eum_string.find(trace_id) != -1
    assert eum_string.find(eum_api_key) != -1
    assert eum_string.find(meta1) != -1
    assert eum_string.find(meta2) != -1
    assert eum_string.find(meta3) != -1


def test_eum_test_snippet_error():
    meta_kvs = {}
    meta_kvs['meta1'] = meta1
    meta_kvs['meta2'] = meta2
    meta_kvs['meta3'] = meta3

    # No active span on tracer & no trace_id passed in.
    eum_string = eum_test_snippet(eum_api_key=eum_api_key, meta=meta_kvs)
    assert_equals('', eum_string)
