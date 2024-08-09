# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2018


# Usage:
#
# from instana.helpers import eum_snippet
# meta_kvs = { 'userId': user.id }
# eum_snippet(meta=meta_kvs)


def eum_snippet(trace_id=None, eum_api_key=None, meta=None):
    """
    This method has been deprecated and will be removed in a future version.

    @param trace_id [optional] the trace ID to insert into the EUM string
    @param eum_api_key [optional] the EUM API key from your Instana dashboard
    @param meta [optional] optional additional KVs you want reported with the
                EUM metrics

    @return string
    """
    return ""


def eum_test_snippet(trace_id=None, eum_api_key=None, meta=None):
    """
    This method has been deprecated and will be removed in a future version.

    @param trace_id [optional] the trace ID to insert into the EUM string
    @param eum_api_key [optional] the EUM API key from your Instana dashboard
    @param meta [optional] optional additional KVs you want reported with the
                EUM metrics

    @return string
    """
    return ""
