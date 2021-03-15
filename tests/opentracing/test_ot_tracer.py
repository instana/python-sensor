# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2020

import opentracing


def test_tracer_basics():
    assert hasattr(opentracing.tracer, "start_span")
    assert hasattr(opentracing.tracer, "inject")
    assert hasattr(opentracing.tracer, "extract")
