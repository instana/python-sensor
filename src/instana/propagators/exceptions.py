# (c) Copyright IBM Corp. 2024


class UnsupportedFormatException(Exception):
    """UnsupportedFormatException should be used when the provided format
    value is unknown or disallowed by the :class:`InstanaTracer`.

    See :meth:`InstanaTracer.inject()` and :meth:`InstanaTracer.extract()`.
    """

    pass
