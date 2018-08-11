import os
from string import Template

from instana import eum_api_key as global_eum_api_key
from .singletons import tracer
from instana.log import logger

# Usage:
#
# from instana.helpers import eum_snippet
# meta_kvs = { 'userId': user.id }
# eum_snippet(meta=meta_kvs)


def eum_snippet(trace_id=None, eum_api_key=None, meta={}):
    """
    Return an EUM snippet for use in views, templates and layouts that reports
    client side metrics to Instana that will automagically be linked to the
    current trace.

    @param trace_id [optional] the trace ID to insert into the EUM string
    @param eum_api_key [optional] the EUM API key from your Instana dashboard
    @param meta [optional] optional additional KVs you want reported with the
                EUM metrics

    @return string
    """
    try:
        eum_file = open(os.path.dirname(__file__) + '/eum.js')
        eum_src = Template(eum_file.read())

        # Prepare the standard required IDs
        ids = {}
        ids['meta_kvs'] = ''

        parent_span = tracer.active_span

        if trace_id or parent_span:
            ids['trace_id'] = trace_id or parent_span.trace_id
        else:
            # No trace_id passed in and tracer doesn't show an active span so
            # return nothing, nada & zip.
            return ''

        if eum_api_key:
            ids['eum_api_key'] = eum_api_key
        else:
            ids['eum_api_key'] = global_eum_api_key

        # Process passed in EUM 'meta' key/values
        for key, value in meta.items():
            ids['meta_kvs'] += ("'ineum('meta', '%s', '%s');'" % (key, value))

        return eum_src.substitute(ids)
    except Exception as e:
        logger.debug(e)
        return ''

def eum_test_snippet(trace_id=None, eum_api_key=None, meta={}):
    """
    Return an EUM snippet for use in views, templates and layouts that reports
    client side metrics to Instana that will automagically be linked to the
    current trace.

    @param trace_id [optional] the trace ID to insert into the EUM string
    @param eum_api_key [optional] the EUM API key from your Instana dashboard
    @param meta [optional] optional additional KVs you want reported with the
                EUM metrics

    @return string
    """

    try:
        eum_file = open(os.path.dirname(__file__) + '/eum_test.js')
        eum_src = Template(eum_file.read())

        # Prepare the standard required IDs
        ids = {}
        ids['meta_kvs'] = ''

        parent_span = tracer.active_span
        if trace_id or parent_span:
            ids['trace_id'] = trace_id or parent_span.trace_id
        else:
            # No trace_id passed in and tracer doesn't show an active span so
            # return nothing, nada & zip.
            return ''

        if eum_api_key:
            ids['eum_api_key'] = eum_api_key
        else:
            ids['eum_api_key'] = global_eum_api_key

        # Process passed in EUM 'meta' key/values
        for key, value in meta.items():
            ids['meta_kvs'] += ("'ineum('meta', '%s', '%s');'" % (key, value))

        return eum_src.substitute(ids)
    except Exception as e:
        logger.debug(e)
        return ''
