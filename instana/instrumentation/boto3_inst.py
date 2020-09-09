from __future__ import absolute_import

import wrapt

from ..log import logger
from ..singletons import tracer

try:
    import botocore
except ImportError:
    pass