# (c) Copyright IBM Corp. 2024


class Format(object):
    """A namespace for builtin carrier formats.

    These static constants are intended for use in the :meth:`Tracer.inject()`
    and :meth:`Tracer.extract()` methods. E.g.::

        tracer.inject(span.context, Format.BINARY, binary_carrier)

    """

    BINARY = "binary"
    """
    The BINARY format represents SpanContexts in an opaque bytearray carrier.

    For both :meth:`Tracer.inject()` and :meth:`Tracer.extract()` the carrier
    should be a bytearray instance. :meth:`Tracer.inject()` must append to the
    bytearray carrier (rather than replace its contents).
    """

    TEXT_MAP = "text_map"
    """
    The TEXT_MAP format represents :class:`SpanContext`\\ s in a python
    ``dict`` mapping from strings to strings.

    Both the keys and the values have unrestricted character sets (unlike the
    HTTP_HEADERS format).

    NOTE: The TEXT_MAP carrier ``dict`` may contain unrelated data (e.g.,
    arbitrary gRPC metadata). As such, the :class:`Tracer` implementation
    should use a prefix or other convention to distinguish tracer-specific
    key:value pairs.
    """

    HTTP_HEADERS = "http_headers"
    """
    The HTTP_HEADERS format represents :class:`SpanContext`\\ s in a python
    ``dict`` mapping from character-restricted strings to strings.

    Keys and values in the HTTP_HEADERS carrier must be suitable for use as
    HTTP headers (without modification or further escaping). That is, the
    keys have a greatly restricted character set, casing for the keys may not
    be preserved by various intermediaries, and the values should be
    URL-escaped.

    NOTE: The HTTP_HEADERS carrier ``dict`` may contain unrelated data (e.g.,
    arbitrary gRPC metadata). As such, the :class:`Tracer` implementation
    should use a prefix or other convention to distinguish tracer-specific
    key:value pairs.
    """

    KAFKA_HEADERS = "kafka_headers"
    """
    The KAFKA_HEADERS format represents :class:`SpanContext`\\ s in a python
    ``dict`` mapping from character-restricted strings to strings.

    Keys and values in the KAFKA_HEADERS carrier must be suitable for use as
    HTTP headers (without modification or further escaping). That is, the
    keys have a greatly restricted character set, casing for the keys may not
    be preserved by various intermediaries, and the values should be
    URL-escaped.
    """
