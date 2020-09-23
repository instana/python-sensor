from __future__ import absolute_import

import wrapt
from ....log import logger

try:
    from google.cloud import storage

    def collect_params(api_request):
        logger.debug('uninstrumented Google Cloud Storage API request: %s' % api_request)

    def execute_with_instana(wrapped, instance, args, kwargs):
        print(collect_params(kwargs))

        return wrapped(*args, **kwargs)

    wrapt.wrap_function_wrapper('google.cloud.storage._http', 'Connection.api_request', execute_with_instana)
except ImportError:
    pass
