# (c) Copyright IBM Corp. 2024

from typing import TYPE_CHECKING, Type
import six

from instana.log import logger
from instana.util import DictionaryOfStan
from instana.span.kind import ENTRY_SPANS

if TYPE_CHECKING:
    from opentelemetry.trace import Span


class BaseSpan(object):
    sy = None

    def __str__(self) -> str:
        return "BaseSpan(%s)" % self.__dict__.__str__()

    def __repr__(self) -> str:
        return self.__dict__.__str__()

    def __init__(self, span: Type["Span"], source, **kwargs) -> None:
        # pylint: disable=invalid-name
        self.t = span.context.trace_id
        self.p = span.parent_id
        self.s = span.context.span_id
        self.ts = round(span.start_time / 10**6)
        self.d = round(span.duration / 10**6) if span.duration else None
        self.f = source
        self.ec = span.attributes.pop("ec", None)
        self.data = DictionaryOfStan()
        self.stack = span.stack

        if span.synthetic is True and span.name in ENTRY_SPANS:
            self.sy = span.synthetic

        self.__dict__.update(kwargs)

    def _populate_extra_span_attributes(self, span) -> None:
        if span.context.trace_parent:
            self.tp = span.context.trace_parent
        if span.context.instana_ancestor:
            self.ia = span.context.instana_ancestor
        if span.context.long_trace_id:
            self.lt = span.context.long_trace_id
        if span.context.correlation_type:
            self.crtp = span.context.correlation_type
        if span.context.correlation_id:
            self.crid = span.context.correlation_id

    def _validate_attributes(self, attributes):
        """
        This method will loop through a set of attributes to validate each key and value.

        :param attributes: dict of attributes
        :return: dict - a filtered set of attributes
        """
        filtered_attributes = DictionaryOfStan()
        for key in attributes.keys():
            validated_key, validated_value = self._validate_attribute(
                key, attributes[key]
            )
            if validated_key is not None and validated_value is not None:
                filtered_attributes[validated_key] = validated_value
        return filtered_attributes

    def _validate_attribute(self, key, value):
        """
        This method will assure that <key> and <value> are valid to set as a attribute.
        If <value> fails the check, an attempt will be made to convert it into
        something useful.

        On check failure, this method will return None values indicating that the attribute is
        not valid and could not be converted into something useful

        :param key: The attribute key
        :param value: The attribute value
        :return: Tuple (key, value)
        """
        validated_key = None
        validated_value = None

        try:
            # Attribute keys must be some type of text or string type
            if isinstance(key, (six.text_type, six.string_types)):
                validated_key = key[0:1024]  # Max key length of 1024 characters

                if isinstance(
                    value,
                    (bool, float, int, list, dict, six.text_type, six.string_types),
                ):
                    validated_value = value
                else:
                    validated_value = self._convert_attribute_value(value)
            else:
                logger.debug(
                    "(non-fatal) attribute names must be strings. attribute discarded for %s",
                    type(key),
                )
        except Exception:
            logger.debug("instana.span._validate_attribute: ", exc_info=True)

        return (validated_key, validated_value)

    def _convert_attribute_value(self, value):
        final_value = None

        try:
            final_value = repr(value)
        except Exception:
            final_value = (
                "(non-fatal) span.set_attribute: values must be one of these types: bool, float, int, list, "
                "set, str or alternatively support 'repr'. attribute discarded"
            )
            logger.debug(final_value, exc_info=True)
            return None
        return final_value
