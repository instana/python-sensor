# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019


import copy
from typing import Any, Callable, Dict, Optional, Tuple

import wrapt

from instana.instrumentation.pep0249 import ConnectionFactory
from instana.log import logger

try:
    import psycopg2
    import psycopg2.extras  # noqa: F401

    cf = ConnectionFactory(connect_func=psycopg2.connect, module_name="postgres")

    setattr(psycopg2, "connect", cf)
    if hasattr(psycopg2, "Connect"):
        setattr(psycopg2, "Connect", cf)

    @wrapt.patch_function_wrapper("psycopg2.extensions", "register_type")
    def register_type_with_instana(
        wrapped: Callable[..., Any],
        instance: Optional[Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Callable[..., object]:
        args_clone = list(copy.copy(args))

        if (len(args_clone) >= 2) and hasattr(args_clone[1], "__wrapped__"):
            args_clone[1] = args_clone[1].__wrapped__

        return wrapped(*args_clone, **kwargs)

    @wrapt.patch_function_wrapper("psycopg2._json", "register_json")
    def register_json_with_instana(
        wrapped: Callable[..., Any],
        instance: Optional[Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
    ) -> Callable[..., object]:
        if "conn_or_curs" in kwargs and hasattr(kwargs["conn_or_curs"], "__wrapped__"):
            kwargs["conn_or_curs"] = kwargs["conn_or_curs"].__wrapped__

        return wrapped(*args, **kwargs)

    logger.debug("Instrumenting psycopg2")
except ImportError:
    pass
