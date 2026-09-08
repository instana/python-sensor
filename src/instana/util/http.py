# (C) Copyright IBM Corp. 2026.

"""HTTP utility helpers for tracer instrumentation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from instana.options import BaseOptions


def should_mark_http_exit_as_error(status_code: int, opts: "BaseOptions") -> bool:
    """Return True if an HTTP exit span with *status_code* should be marked as errored.

    Rules (in priority order):
    1. status >= 500 → always an error.
    2. 400 <= status <= 499 and ``opts.http_exit_classify_as_errors`` is non-empty
       → error only if *status_code* is in that list.
    3. 400 <= status <= 499 and ``opts.http_exit_classify_all_4xx_as_errors`` is True
       → error for every 4xx code.
    4. Otherwise → not an error.

    Entry (server) spans are never passed here; this function is for exit spans only.
    """
    if status_code >= 500:
        return True
    if 400 <= status_code <= 499:
        if opts.http_exit_classify_as_errors:
            return status_code in opts.http_exit_classify_as_errors
        return opts.http_exit_classify_all_4xx_as_errors
    return False
