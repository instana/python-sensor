# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017

"""
This module contains the classes that represents spans.

InstanaSpan - the OpenTelemetry based span used during tracing

When an InstanaSpan is finished, it is converted into either an SDKSpan
or RegisteredSpan depending on type.

BaseSpan: Base class containing the commonalities for the two descendants
  - SDKSpan: Class that represents an SDK type span
  - RegisteredSpan: Class that represents a Registered type span
"""
import six
from typing import Dict, Optional, Union, Sequence, Tuple
from threading import Lock
from time import time_ns

from opentelemetry.trace import Span  # , SpanContext
from opentelemetry.util import types
from opentelemetry.trace.status import Status, StatusCode

from .span_context import SpanContext
from .log import logger
from .util import DictionaryOfStan


class Event:
    def __init__(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
    ) -> None:
        self._name = name
        self._attributes = attributes
        if timestamp is None:
            self._timestamp = time_ns()
        else:
            self._timestamp = timestamp

    @property
    def name(self) -> str:
        return self._name

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @property
    def attributes(self) -> types.Attributes:
        return self._attributes


class InstanaSpan(Span):
    stack = None
    synthetic = False

    def __init__(
        self,
        name: str,
        context: SpanContext,
        parent_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        attributes: types.Attributes = {},
        events: Sequence[Event] = [],
        status: Optional[Status] = Status(StatusCode.UNSET),
    ) -> None:
        self._name = name
        self._context = context
        self._lock = Lock()
        self._start_time = start_time or time_ns()
        self._end_time = end_time
        self._duration = 0
        self._attributes = attributes
        self._events = events
        self._parent_id = parent_id
        self._status = status

        if context.synthetic:
            self.synthetic = True


    @property
    def name(self) -> str:
        return self._name

    def get_span_context(self) -> SpanContext:
        return self._context

    @property
    def context(self) -> SpanContext:
        return self._context

    @property
    def start_time(self) -> Optional[int]:
        return self._start_time

    @property
    def end_time(self) -> Optional[int]:
        return self._end_time
    
    @property
    def duration(self) -> int:
        return self._duration

    @property
    def attributes(self) -> types.Attributes:
        return self._attributes

    def set_attributes(self, attributes: Dict[str, types.AttributeValue]) -> None:
        if not self._attributes:
            self._attributes = {}

        with self._lock:
            for key, value in attributes.items():
                self._attributes[key] = value

    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        return self.set_attributes({key: value})

    @property
    def events(self) -> Sequence[Event]:
        return self._events

    @property
    def status(self) -> Status:
        return self._status
    
    @property
    def parent_id(self) -> int:
        return self._parent_id

    def update_name(self, name: str) -> None:
        with self._lock:
            self._name = name

    def is_recording(self) -> bool:
        return self._end_time is None

    def set_status(
        self,
        status: Union[Status, StatusCode],
        description: Optional[str] = None,
    ) -> None:
        # Ignore future calls if status is already set to OK
        # Ignore calls to set to StatusCode.UNSET
        if isinstance(status, Status):
            if (
                self._status
                and self._status.status_code is StatusCode.OK
                or status.status_code is StatusCode.UNSET
            ):
                return
            if description is not None:
                logger.warning(
                    "Description %s ignored. Use either `Status` or `(StatusCode, Description)`",
                    description,
                )
            self._status = status
        elif isinstance(status, StatusCode):
            if (
                self._status
                and self._status.status_code is StatusCode.OK
                or status is StatusCode.UNSET
            ):
                return
            self._status = Status(status, description)

    def add_event(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
    ) -> None:

        event = Event(
            name=name,
            attributes=attributes,
            timestamp=timestamp,
        )

        self._events.append(event)

    def record_exception(
        self,
        exception: Exception,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
        escaped: bool = False,
    ) -> None:
        """
        Records an exception as a span event. This will record pertinent info from the exception and
        assure that this span is marked as errored.
        """
        try:
            message = ""
            self.mark_as_errored()
            if hasattr(exception, "__str__") and len(str(exception)) > 0:
                message = str(exception)
            elif hasattr(exception, "message") and exception.message is not None:
                message = exception.message
            else:
                message = repr(exception)

            if self.name in ["rpc-server", "rpc-client"]:
                self.set_attribute("rpc.error", message)
            elif self.name == "mysql":
                self.set_attribute("mysql.error", message)
            elif self.name == "postgres":
                self.set_attribute("pg.error", message)
            elif self.name in RegisteredSpan.HTTP_SPANS:
                self.set_attribute("http.error", message)
            elif self.name in ["celery-client", "celery-worker"]:
                self.set_attribute("error", message)
            elif self.name == "sqlalchemy":
                self.set_attribute("sqlalchemy.err", message)
            elif self.name == "aws.lambda.entry":
                self.set_attribute("lambda.error", message)
            else:
                _attributes = {"message": message}
                if attributes:
                    _attributes.update(attributes)
                self.add_event(
                    name="exception", attributes=_attributes, timestamp=timestamp
                )
        except Exception:
            logger.debug("span.record_exception", exc_info=True)
            raise

    def end(self, end_time: Optional[int] = None) -> None:
        with self._lock:
            self._end_time = end_time if end_time is not None else time_ns()
            self._duration = self._end_time - self._start_time

    def mark_as_errored(self, attributes: types.Attributes = None) -> None:
        """
        Mark this span as errored.

        @param attributes: optional attributes to add to the span
        """
        try:
            ec = self.attributes.get("ec", 0)
            self.set_attribute("ec", ec + 1)

            if attributes is not None and isinstance(attributes, dict):
                for key in attributes:
                    self.set_attribute(key, attributes[key])
        except Exception:
            logger.debug("span.mark_as_errored", exc_info=True)

    def assure_errored(self) -> None:
        """
        Make sure that this span is marked as errored.
        @return: None
        """
        try:
            ec = self.attributes.get("ec", None)
            if ec is None or ec == 0:
                self.set_attribute("ec", 1)
        except Exception:
            logger.debug("span.assure_errored", exc_info=True)


class BaseSpan(object):
    sy = None

    def __str__(self) -> str:
        return "BaseSpan(%s)" % self.__dict__.__str__()

    def __repr__(self) -> str:
        return self.__dict__.__str__()

    def __init__(self, span, source, service_name, **kwargs) -> None:
        # pylint: disable=invalid-name
        self.t = span.context.trace_id
        self.p = span.parent_id
        # self.p = span.context.span_id if span.context.is_remote else None
        self.s = span.context.span_id
        self.ts = round(span.start_time / 10**6)
        self.d = round(span.duration / 10**6)
        self.f = source
        self.ec = span.attributes.pop("ec", None)
        self.data = DictionaryOfStan()
        self.stack = span.stack

        if span.synthetic is True:
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


class SDKSpan(BaseSpan):
    ENTRY_KIND = ["entry", "server", "consumer"]
    EXIT_KIND = ["exit", "client", "producer"]

    def __init__(self, span, source, service_name, **kwargs) -> None:
        # pylint: disable=invalid-name
        super(SDKSpan, self).__init__(span, source, service_name, **kwargs)

        span_kind = self.get_span_kind(span)

        self.n = "sdk"
        self.k = span_kind[1]

        if service_name is not None:
            self.data["service"] = service_name

        self.data["sdk"]["name"] = span.name
        self.data["sdk"]["type"] = span_kind[0]
        self.data["sdk"]["custom"]["attributes"] = self._validate_attributes(
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
            if span.attributes["span.kind"] in self.ENTRY_KIND:
                kind = ("entry", 1)
            elif span.attributes["span.kind"] in self.EXIT_KIND:
                kind = ("exit", 2)
        return kind


class RegisteredSpan(BaseSpan):
    HTTP_SPANS = (
        "aiohttp-client",
        "aiohttp-server",
        "django",
        "http",
        "tornado-client",
        "tornado-server",
        "urllib3",
        "wsgi",
        "asgi",
    )

    EXIT_SPANS = (
        "aiohttp-client",
        "boto3",
        "cassandra",
        "celery-client",
        "couchbase",
        "log",
        "memcache",
        "mongo",
        "mysql",
        "postgres",
        "rabbitmq",
        "redis",
        "rpc-client",
        "sqlalchemy",
        "tornado-client",
        "urllib3",
        "pymongo",
        "gcs",
        "gcps-producer",
    )

    ENTRY_SPANS = (
        "aiohttp-server",
        "aws.lambda.entry",
        "celery-worker",
        "django",
        "wsgi",
        "rabbitmq",
        "rpc-server",
        "tornado-server",
        "gcps-consumer",
        "asgi",
    )

    LOCAL_SPANS = "render"

    def __init__(self, span, source, service_name, **kwargs) -> None:
        # pylint: disable=invalid-name
        super(RegisteredSpan, self).__init__(span, source, service_name, **kwargs)
        self.n = span.name
        self.k = 1

        self.data["service"] = service_name
        if span.name in self.ENTRY_SPANS:
            # entry
            self._populate_entry_span_data(span)
            self._populate_extra_span_attributes(span)
        elif span.name in self.EXIT_SPANS:
            self.k = 2  # exit
            self._populate_exit_span_data(span)
        elif span.name in self.LOCAL_SPANS:
            self.k = 3  # intermediate span
            self._populate_local_span_data(span)

        if "rabbitmq" in self.data and self.data["rabbitmq"]["sort"] == "publish":
            self.k = 2  # exit

        # unify the span name for gcps-producer and gcps-consumer
        if "gcps" in span.name:
            self.n = "gcps"

        # Store any leftover attributes in the custom section
        if len(span.attributes) > 0:
            self.data["custom"]["attributes"] = self._validate_attributes(
                span.attributes
            )

    def _populate_entry_span_data(self, span) -> None:
        if span.name in self.HTTP_SPANS:
            self._collect_http_attributes(span)

        elif span.name == "aws.lambda.entry":
            self.data["lambda"]["arn"] = span.attributes.pop("lambda.arn", "Unknown")
            self.data["lambda"]["alias"] = None
            self.data["lambda"]["runtime"] = "python"
            self.data["lambda"]["functionName"] = span.attributes.pop(
                "lambda.name", "Unknown"
            )
            self.data["lambda"]["functionVersion"] = span.attributes.pop(
                "lambda.version", "Unknown"
            )
            self.data["lambda"]["trigger"] = span.attributes.pop("lambda.trigger", None)
            self.data["lambda"]["error"] = span.attributes.pop("lambda.error", None)

            trigger_type = self.data["lambda"]["trigger"]

            if trigger_type in ["aws:api.gateway", "aws:application.load.balancer"]:
                self._collect_http_attributes(span)
            elif trigger_type == "aws:cloudwatch.events":
                self.data["lambda"]["cw"]["events"]["id"] = span.attributes.pop(
                    "data.lambda.cw.events.id", None
                )
                self.data["lambda"]["cw"]["events"]["more"] = span.attributes.pop(
                    "lambda.cw.events.more", False
                )
                self.data["lambda"]["cw"]["events"]["resources"] = span.attributes.pop(
                    "lambda.cw.events.resources", None
                )

            elif trigger_type == "aws:cloudwatch.logs":
                self.data["lambda"]["cw"]["logs"]["group"] = span.attributes.pop(
                    "lambda.cw.logs.group", None
                )
                self.data["lambda"]["cw"]["logs"]["stream"] = span.attributes.pop(
                    "lambda.cw.logs.stream", None
                )
                self.data["lambda"]["cw"]["logs"]["more"] = span.attributes.pop(
                    "lambda.cw.logs.more", None
                )
                self.data["lambda"]["cw"]["logs"]["events"] = span.attributes.pop(
                    "lambda.cw.logs.events", None
                )

            elif trigger_type == "aws:s3":
                self.data["lambda"]["s3"]["events"] = span.attributes.pop(
                    "lambda.s3.events", None
                )
            elif trigger_type == "aws:sqs":
                self.data["lambda"]["sqs"]["messages"] = span.attributes.pop(
                    "lambda.sqs.messages", None
                )

        elif span.name == "celery-worker":
            self.data["celery"]["task"] = span.attributes.pop("task", None)
            self.data["celery"]["task_id"] = span.attributes.pop("task_id", None)
            self.data["celery"]["scheme"] = span.attributes.pop("scheme", None)
            self.data["celery"]["host"] = span.attributes.pop("host", None)
            self.data["celery"]["port"] = span.attributes.pop("port", None)
            self.data["celery"]["retry-reason"] = span.attributes.pop(
                "retry-reason", None
            )
            self.data["celery"]["error"] = span.attributes.pop("error", None)

        elif span.name == "gcps-consumer":
            self.data["gcps"]["op"] = span.attributes.pop("gcps.op", None)
            self.data["gcps"]["projid"] = span.attributes.pop("gcps.projid", None)
            self.data["gcps"]["sub"] = span.attributes.pop("gcps.sub", None)

        elif span.name == "rabbitmq":
            self.data["rabbitmq"]["exchange"] = span.attributes.pop("exchange", None)
            self.data["rabbitmq"]["queue"] = span.attributes.pop("queue", None)
            self.data["rabbitmq"]["sort"] = span.attributes.pop("sort", None)
            self.data["rabbitmq"]["address"] = span.attributes.pop("address", None)
            self.data["rabbitmq"]["key"] = span.attributes.pop("key", None)

        elif span.name == "rpc-server":
            self.data["rpc"]["flavor"] = span.attributes.pop("rpc.flavor", None)
            self.data["rpc"]["host"] = span.attributes.pop("rpc.host", None)
            self.data["rpc"]["port"] = span.attributes.pop("rpc.port", None)
            self.data["rpc"]["call"] = span.attributes.pop("rpc.call", None)
            self.data["rpc"]["call_type"] = span.attributes.pop("rpc.call_type", None)
            self.data["rpc"]["params"] = span.attributes.pop("rpc.params", None)
            # self.data["rpc"]["baggage"] = span.attributes.pop("rpc.baggage", None)
            self.data["rpc"]["error"] = span.attributes.pop("rpc.error", None)
        else:
            logger.debug("SpanRecorder: Unknown entry span: %s" % span.name)

    def _populate_local_span_data(self, span) -> None:
        if span.name == "render":
            self.data["render"]["name"] = span.attributes.pop("name", None)
            self.data["render"]["type"] = span.attributes.pop("type", None)
            self.data["event"]["message"] = span.attributes.pop("message", None)
            self.data["event"]["parameters"] = span.attributes.pop("parameters", None)
        else:
            logger.debug("SpanRecorder: Unknown local span: %s" % span.name)

    def _populate_exit_span_data(self, span) -> None:
        if span.name in self.HTTP_SPANS:
            self._collect_http_attributes(span)

        elif span.name == "boto3":
            # boto3 also sends http attributes
            self._collect_http_attributes(span)

            for attribute in ["op", "ep", "reg", "payload", "error"]:
                value = span.attributes.pop(attribute, None)
                if value is not None:
                    if attribute == "payload":
                        self.data["boto3"][attribute] = self._validate_attributes(value)
                    else:
                        self.data["boto3"][attribute] = value

        elif span.name == "cassandra":
            self.data["cassandra"]["cluster"] = span.attributes.pop(
                "cassandra.cluster", None
            )
            self.data["cassandra"]["query"] = span.attributes.pop(
                "cassandra.query", None
            )
            self.data["cassandra"]["keyspace"] = span.attributes.pop(
                "cassandra.keyspace", None
            )
            self.data["cassandra"]["fetchSize"] = span.attributes.pop(
                "cassandra.fetchSize", None
            )
            self.data["cassandra"]["achievedConsistency"] = span.attributes.pop(
                "cassandra.achievedConsistency", None
            )
            self.data["cassandra"]["triedHosts"] = span.attributes.pop(
                "cassandra.triedHosts", None
            )
            self.data["cassandra"]["fullyFetched"] = span.attributes.pop(
                "cassandra.fullyFetched", None
            )
            self.data["cassandra"]["error"] = span.attributes.pop(
                "cassandra.error", None
            )

        elif span.name == "celery-client":
            self.data["celery"]["task"] = span.attributes.pop("task", None)
            self.data["celery"]["task_id"] = span.attributes.pop("task_id", None)
            self.data["celery"]["scheme"] = span.attributes.pop("scheme", None)
            self.data["celery"]["host"] = span.attributes.pop("host", None)
            self.data["celery"]["port"] = span.attributes.pop("port", None)
            self.data["celery"]["error"] = span.attributes.pop("error", None)

        elif span.name == "couchbase":
            self.data["couchbase"]["hostname"] = span.attributes.pop(
                "couchbase.hostname", None
            )
            self.data["couchbase"]["bucket"] = span.attributes.pop(
                "couchbase.bucket", None
            )
            self.data["couchbase"]["type"] = span.attributes.pop("couchbase.type", None)
            self.data["couchbase"]["error"] = span.attributes.pop(
                "couchbase.error", None
            )
            self.data["couchbase"]["error_type"] = span.attributes.pop(
                "couchbase.error_type", None
            )
            self.data["couchbase"]["sql"] = span.attributes.pop("couchbase.sql", None)

        elif span.name == "rabbitmq":
            self.data["rabbitmq"]["exchange"] = span.attributes.pop("exchange", None)
            self.data["rabbitmq"]["queue"] = span.attributes.pop("queue", None)
            self.data["rabbitmq"]["sort"] = span.attributes.pop("sort", None)
            self.data["rabbitmq"]["address"] = span.attributes.pop("address", None)
            self.data["rabbitmq"]["key"] = span.attributes.pop("key", None)

        elif span.name == "redis":
            self.data["redis"]["connection"] = span.attributes.pop("connection", None)
            self.data["redis"]["driver"] = span.attributes.pop("driver", None)
            self.data["redis"]["command"] = span.attributes.pop("command", None)
            self.data["redis"]["error"] = span.attributes.pop("redis.error", None)
            self.data["redis"]["subCommands"] = span.attributes.pop("subCommands", None)

        elif span.name == "rpc-client":
            self.data["rpc"]["flavor"] = span.attributes.pop("rpc.flavor", None)
            self.data["rpc"]["host"] = span.attributes.pop("rpc.host", None)
            self.data["rpc"]["port"] = span.attributes.pop("rpc.port", None)
            self.data["rpc"]["call"] = span.attributes.pop("rpc.call", None)
            self.data["rpc"]["call_type"] = span.attributes.pop("rpc.call_type", None)
            self.data["rpc"]["params"] = span.attributes.pop("rpc.params", None)
            # self.data["rpc"]["baggage"] = span.attributes.pop("rpc.baggage", None)
            self.data["rpc"]["error"] = span.attributes.pop("rpc.error", None)

        elif span.name == "sqlalchemy":
            self.data["sqlalchemy"]["sql"] = span.attributes.pop("sqlalchemy.sql", None)
            self.data["sqlalchemy"]["eng"] = span.attributes.pop("sqlalchemy.eng", None)
            self.data["sqlalchemy"]["url"] = span.attributes.pop("sqlalchemy.url", None)
            self.data["sqlalchemy"]["err"] = span.attributes.pop("sqlalchemy.err", None)

        elif span.name == "mysql":
            self.data["mysql"]["host"] = span.attributes.pop("host", None)
            self.data["mysql"]["port"] = span.attributes.pop("port", None)
            self.data["mysql"]["db"] = span.attributes.pop("db.instance", None)
            self.data["mysql"]["user"] = span.attributes.pop("db.user", None)
            self.data["mysql"]["stmt"] = span.attributes.pop("db.statement", None)
            self.data["mysql"]["error"] = span.attributes.pop("mysql.error", None)

        elif span.name == "postgres":
            self.data["pg"]["host"] = span.attributes.pop("host", None)
            self.data["pg"]["port"] = span.attributes.pop("port", None)
            self.data["pg"]["db"] = span.attributes.pop("db.instance", None)
            self.data["pg"]["user"] = span.attributes.pop("db.user", None)
            self.data["pg"]["stmt"] = span.attributes.pop("db.statement", None)
            self.data["pg"]["error"] = span.attributes.pop("pg.error", None)

        elif span.name == "mongo":
            service = "%s:%s" % (
                span.attributes.pop("host", None),
                span.attributes.pop("port", None),
            )
            namespace = "%s.%s" % (
                span.attributes.pop("db", "?"),
                span.attributes.pop("collection", "?"),
            )

            self.data["mongo"]["service"] = service
            self.data["mongo"]["namespace"] = namespace
            self.data["mongo"]["command"] = span.attributes.pop("command", None)
            self.data["mongo"]["filter"] = span.attributes.pop("filter", None)
            self.data["mongo"]["json"] = span.attributes.pop("json", None)
            self.data["mongo"]["error"] = span.attributes.pop("error", None)

        elif span.name == "gcs":
            self.data["gcs"]["op"] = span.attributes.pop("gcs.op", None)
            self.data["gcs"]["bucket"] = span.attributes.pop("gcs.bucket", None)
            self.data["gcs"]["object"] = span.attributes.pop("gcs.object", None)
            self.data["gcs"]["entity"] = span.attributes.pop("gcs.entity", None)
            self.data["gcs"]["range"] = span.attributes.pop("gcs.range", None)
            self.data["gcs"]["sourceBucket"] = span.attributes.pop(
                "gcs.sourceBucket", None
            )
            self.data["gcs"]["sourceObject"] = span.attributes.pop(
                "gcs.sourceObject", None
            )
            self.data["gcs"]["sourceObjects"] = span.attributes.pop(
                "gcs.sourceObjects", None
            )
            self.data["gcs"]["destinationBucket"] = span.attributes.pop(
                "gcs.destinationBucket", None
            )
            self.data["gcs"]["destinationObject"] = span.attributes.pop(
                "gcs.destinationObject", None
            )
            self.data["gcs"]["numberOfOperations"] = span.attributes.pop(
                "gcs.numberOfOperations", None
            )
            self.data["gcs"]["projectId"] = span.attributes.pop("gcs.projectId", None)
            self.data["gcs"]["accessId"] = span.attributes.pop("gcs.accessId", None)

        elif span.name == "gcps-producer":
            self.data["gcps"]["op"] = span.attributes.pop("gcps.op", None)
            self.data["gcps"]["projid"] = span.attributes.pop("gcps.projid", None)
            self.data["gcps"]["top"] = span.attributes.pop("gcps.top", None)

        elif span.name == "log":
            # use last special key values
            for event in span.events:
                if "message" in event.attributes:
                    self.data["event"]["message"] = event.attributes.pop(
                        "message", None
                    )
                if "parameters" in event.attributes:
                    self.data["event"]["parameters"] = event.attributes.pop(
                        "parameters", None
                    )
        else:
            logger.debug("SpanRecorder: Unknown exit span: %s" % span.name)

    def _collect_http_attributes(self, span) -> None:
        self.data["http"]["host"] = span.attributes.pop("http.host", None)
        self.data["http"]["url"] = span.attributes.pop("http.url", None)
        self.data["http"]["path"] = span.attributes.pop("http.path", None)
        self.data["http"]["params"] = span.attributes.pop("http.params", None)
        self.data["http"]["method"] = span.attributes.pop("http.method", None)
        self.data["http"]["status"] = span.attributes.pop("http.status_code", None)
        self.data["http"]["path_tpl"] = span.attributes.pop("http.path_tpl", None)
        self.data["http"]["error"] = span.attributes.pop("http.error", None)

        if len(span.attributes) > 0:
            custom_headers = []
            for key in span.attributes:
                if key[0:12] == "http.header.":
                    custom_headers.append(key)

            for key in custom_headers:
                trimmed_key = key[12:]
                self.data["http"]["header"][trimmed_key] = span.attributes.pop(key)
