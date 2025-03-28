# (c) Copyright IBM Corp. 2024

from typing import TYPE_CHECKING, Any, Dict

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind

from instana.log import logger
from instana.span.base_span import BaseSpan
from instana.span.kind import ENTRY_SPANS, EXIT_SPANS, HTTP_SPANS, LOCAL_SPANS

if TYPE_CHECKING:
    from instana.span.span import InstanaSpan


class RegisteredSpan(BaseSpan):
    def __init__(
        self,
        span: "InstanaSpan",
        source: Dict[str, Any],
        service_name: str,
        **kwargs: Dict[str, Any],
    ) -> None:
        # pylint: disable=invalid-name
        super(RegisteredSpan, self).__init__(span, source, **kwargs)
        self.n = span.name
        self.k = SpanKind.SERVER  # entry -> Server span represents a synchronous incoming remote call such as an incoming HTTP request

        self.data["service"] = service_name
        if span.name in ENTRY_SPANS:
            # entry
            self._populate_entry_span_data(span)
            self._populate_extra_span_attributes(span)
        elif span.name in EXIT_SPANS:
            self.k = SpanKind.CLIENT  # exit -> Client span represents a synchronous outgoing remote call such as an outgoing HTTP request or database call
            self._populate_exit_span_data(span)
        elif span.name in LOCAL_SPANS:
            self.k = SpanKind.INTERNAL  # intermediate -> Internal span represents an internal operation within an application
            self._populate_local_span_data(span)

        if "rabbitmq" in self.data and self.data["rabbitmq"]["sort"] == "publish":
            self.k = SpanKind.CLIENT  # exit

        # unify the span name for gcps-producer and gcps-consumer
        if "gcps" in span.name:
            self.n = "gcps"

        # unify the span name for kafka-producer and kafka-consumer
        if "kafka" in span.name:
            self.n = "kafka"

        # unify the span name for aioamqp-producer and aioamqp-consumer
        if "amqp" in span.name:
            self.n = "amqp"

        # unify the span name for httpx (and future exit HTTP spans)
        if "httpx" in span.name:
            self.n = "http"

        # Logic to store custom attributes for registered spans (not used yet)
        if len(span.attributes) > 0:
            self.data["sdk"]["custom"]["tags"] = self._validate_attributes(
                span.attributes
            )

    def _populate_entry_span_data(self, span: "InstanaSpan") -> None:
        if span.name in HTTP_SPANS:
            self._collect_http_attributes(span)

        elif span.name == "aioamqp-consumer":
            self.data["amqp"]["command"] = span.attributes.pop("amqp.command", None)
            self.data["amqp"]["routingkey"] = span.attributes.pop(
                "amqp.routing_key", None
            )
            self.data["amqp"]["connection"] = span.attributes.pop(
                "amqp.connection", None
            )
            self.data["amqp"]["error"] = span.attributes.pop("amqp.error", None)

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

        elif span.name.startswith("kafka"):
            self._collect_kafka_attributes(span)

        else:
            logger.debug("SpanRecorder: Unknown entry span: %s" % span.name)

    def _populate_local_span_data(self, span: "InstanaSpan") -> None:
        if span.name == "render":
            self.data["render"]["name"] = span.attributes.pop("name", None)
            self.data["render"]["type"] = span.attributes.pop("type", None)
            self.data["log"]["message"] = span.attributes.pop("message", None)
            self.data["log"]["parameters"] = span.attributes.pop("parameters", None)
        else:
            logger.debug("SpanRecorder: Unknown local span: %s" % span.name)

    def _populate_exit_span_data(self, span: "InstanaSpan") -> None:
        if span.name in HTTP_SPANS:
            self._collect_http_attributes(span)

        elif span.name == "aioamqp-publisher":
            self.data["amqp"]["command"] = span.attributes.pop("amqp.command", None)
            self.data["amqp"]["routingkey"] = span.attributes.pop(
                "amqp.routing_key", None
            )
            self.data["amqp"]["connection"] = span.attributes.pop(
                "amqp.connection", None
            )
            self.data["amqp"]["error"] = span.attributes.pop("amqp.error", None)

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

        elif span.name == "dynamodb":
            self.data["dynamodb"]["op"] = span.attributes.pop("dynamodb.op", None)
            self.data["dynamodb"]["region"] = span.attributes.pop(
                "dynamodb.region", None
            )
            self.data["dynamodb"]["table"] = span.attributes.pop("dynamodb.table", None)

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

        elif span.name == "s3":
            self.data["s3"]["op"] = span.attributes.pop("s3.op", None)
            self.data["s3"]["bucket"] = span.attributes.pop("s3.bucket", None)

        elif span.name == "sqlalchemy":
            self.data["sqlalchemy"]["sql"] = span.attributes.pop("sqlalchemy.sql", None)
            self.data["sqlalchemy"]["eng"] = span.attributes.pop("sqlalchemy.eng", None)
            self.data["sqlalchemy"]["url"] = span.attributes.pop("sqlalchemy.url", None)
            self.data["sqlalchemy"]["err"] = span.attributes.pop("sqlalchemy.err", None)

        elif span.name == "mysql":
            self.data["mysql"]["host"] = span.attributes.pop("host", None)
            self.data["mysql"]["port"] = span.attributes.pop("port", None)
            self.data["mysql"]["db"] = span.attributes.pop(SpanAttributes.DB_NAME, None)
            self.data["mysql"]["user"] = span.attributes.pop(
                SpanAttributes.DB_USER, None
            )
            self.data["mysql"]["stmt"] = span.attributes.pop(
                SpanAttributes.DB_STATEMENT, None
            )
            self.data["mysql"]["error"] = span.attributes.pop("mysql.error", None)

        elif span.name == "postgres":
            self.data["pg"]["host"] = span.attributes.pop("host", None)
            self.data["pg"]["port"] = span.attributes.pop("port", None)
            self.data["pg"]["db"] = span.attributes.pop("db.name", None)
            self.data["pg"]["user"] = span.attributes.pop("db.user", None)
            self.data["pg"]["stmt"] = span.attributes.pop("db.statement", None)
            self.data["pg"]["error"] = span.attributes.pop("pg.error", None)

        elif span.name == "mongo":
            service = f"{span.attributes.pop(SpanAttributes.SERVER_ADDRESS, None)}:{span.attributes.pop(SpanAttributes.SERVER_PORT, None)}"
            namespace = f"{span.attributes.pop(SpanAttributes.DB_NAME, '?')}.{span.attributes.pop(SpanAttributes.DB_MONGODB_COLLECTION, '?')}"

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
                    self.data["log"]["message"] = event.attributes.pop("message", None)
                if "parameters" in event.attributes:
                    self.data["log"]["parameters"] = event.attributes.pop(
                        "parameters", None
                    )

        elif span.name.startswith("kafka"):
            self._collect_kafka_attributes(span)

        else:
            logger.debug("SpanRecorder: Unknown exit span: %s" % span.name)

    def _collect_http_attributes(self, span: "InstanaSpan") -> None:
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

    def _collect_kafka_attributes(self, span: "InstanaSpan") -> None:
        self.data["kafka"]["service"] = span.attributes.pop("kafka.service", None)
        self.data["kafka"]["access"] = span.attributes.pop("kafka.access", None)
        self.data["kafka"]["error"] = span.attributes.pop("kafka.error", None)
