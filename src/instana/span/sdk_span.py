# (c) Copyright IBM Corp. 2024

from typing import Tuple

from instana.span.base_span import BaseSpan
from instana.span.kind import ENTRY_KIND, EXIT_KIND
from instana.util import DictionaryOfStan


class SDKSpan(BaseSpan):
    def __init__(self, span, source, service_name, **kwargs) -> None:
        # pylint: disable=invalid-name
        super(SDKSpan, self).__init__(span, source, **kwargs)

        span_kind = self.get_span_kind(span)

        self.n = "sdk"
        self.k = span_kind[1]

        if service_name is not None:
            self.data["service"] = service_name

        self.data["sdk"]["name"] = span.name
        self.data["sdk"]["type"] = span_kind[0]
        self.data["sdk"]["custom"]["tags"] = self._validate_attributes(
            span.attributes
        )

        if span.events is not None and len(span.events) > 0:
            events = DictionaryOfStan()
            for event in span.events:
                filtered_attributes = self._validate_attributes(event.attributes)
                if len(filtered_attributes.keys()) > 0:
                    events[repr(event.timestamp)] = filtered_attributes
            self.data["sdk"]["custom"]["events"] = events

        if "arguments" in span.attributes:
            self.data["sdk"]["arguments"] = span.attributes["arguments"]

        if "return" in span.attributes:
            self.data["sdk"]["return"] = span.attributes["return"]

        # if len(span.context.baggage) > 0:
        #     self.data["baggage"] = span.context.baggage

    def get_span_kind(self, span) -> Tuple[str, int]:
        """
        Will retrieve the `span.kind` attribute and return a tuple containing the appropriate string and integer
        values for the Instana backend

        :param span: The span to search for the `span.kind` attribute
        :return: Tuple (String, Int)
        """
        kind = ("intermediate", 3)
        if "span.kind" in span.attributes:
            if span.attributes["span.kind"] in ENTRY_KIND:
                kind = ("entry", 1)
            elif span.attributes["span.kind"] in EXIT_KIND:
                kind = ("exit", 2)
        return kind


