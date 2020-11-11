"""
This module contains the classes that represents spans.

InstanaSpan - the OpenTracing based span used during tracing

When an InstanaSpan is finished, it is converted into either an SDKSpan
or RegisteredSpan depending on type.

BaseSpan: Base class containing the commonalities for the two descendants
  - SDKSpan: Class that represents an SDK type span
  - RegisteredSpan: Class that represents a Registered type span
"""
import six

from basictracer.span import BasicSpan
import opentracing.ext.tags as ot_tags

from .log import logger
from .util import DictionaryOfStan


class InstanaSpan(BasicSpan):
    stack = None
    synthetic = False

    def mark_as_errored(self, tags = None):
        """
        Mark this span as errored.

        @param tags: optional tags to add to the span
        """
        try:
            ec = self.tags.get('ec', 0)
            self.set_tag('ec', ec + 1)

            if tags is not None and isinstance(tags, dict):
                for key in tags:
                    self.set_tag(key, tags[key])
        except Exception:
            logger.debug('span.mark_as_errored', exc_info=True)

    def assure_errored(self):
        """
        Make sure that this span is marked as errored.
        @return: None
        """
        try:
            ec = self.tags.get('ec', None)
            if ec is None or ec == 0:
                self.set_tag('ec', 1)
        except Exception:
            logger.debug('span.assure_errored', exc_info=True)

    def log_exception(self, exc):
        """
        Log an exception onto this span.  This will log pertinent info from the exception and
        assure that this span is marked as errored.

        @param e: the exception to log
        """
        try:
            message = ""
            self.mark_as_errored()

            if hasattr(exc, '__str__') and len(str(exc)) > 0:
                message = str(exc)
            elif hasattr(exc, 'message') and exc.message is not None:
                message = exc.message
            else:
                message = repr(exc)

            if self.operation_name in ['rpc-server', 'rpc-client']:
                self.set_tag('rpc.error', message)
            elif self.operation_name == "mysql":
                self.set_tag('mysql.error', message)
            elif self.operation_name == "postgres":
                self.set_tag('pg.error', message)
            elif self.operation_name in RegisteredSpan.HTTP_SPANS:
                self.set_tag('http.error', message)
            elif self.operation_name in ["celery-client", "celery-worker"]:
                self.set_tag('error', message)
            else:
                self.log_kv({'message': message})
        except Exception:
            logger.debug("span.log_exception", exc_info=True)
            raise

class BaseSpan(object):
    sy = None

    def __str__(self):
        return "BaseSpan(%s)" % self.__dict__.__str__()

    def __repr__(self):
        return self.__dict__.__str__()

    def __init__(self, span, source, service_name, **kwargs):
        # pylint: disable=invalid-name
        self.t = span.context.trace_id
        self.p = span.parent_id
        self.s = span.context.span_id
        self.ts = int(round(span.start_time * 1000))
        self.d = int(round(span.duration * 1000))
        self.f = source
        self.ec = span.tags.pop('ec', None)
        self.data = DictionaryOfStan()

        if span.synthetic:
            self.sy = True

        if span.stack:
            self.stack = span.stack

        self.__dict__.update(kwargs)
    
    def _validate_tags(self, tags):
        """
        This method will loop through a set of tags to validate each key and value.

        :param tags: dict of tags
        :return: dict - a filtered set of tags
        """
        filtered_tags = DictionaryOfStan()
        for key in tags.keys():
            validated_key, validated_value = self._validate_tag(key, tags[key])
            if validated_key is not None and validated_value is not None:
                filtered_tags[validated_key] = validated_value
        return filtered_tags

    def _validate_tag(self, key, value):
        """
        This method will assure that <key> and <value> are valid to set as a tag.
        If <value> fails the check, an attempt will be made to convert it into
        something useful.

        On check failure, this method will return None values indicating that the tag is
        not valid and could not be converted into something useful

        :param key: The tag key
        :param value: The tag value
        :return: Tuple (key, value)
        """
        validated_key = None
        validated_value = None

        try:
            # Tag keys must be some type of text or string type
            if isinstance(key, (six.text_type, six.string_types)):
                validated_key = key[0:1024] # Max key length of 1024 characters

                if isinstance(value, (bool, float, int, list, dict, six.text_type, six.string_types)):
                    validated_value = value
                else:
                    validated_value = self._convert_tag_value(value)
            else:
                logger.debug("(non-fatal) tag names must be strings. tag discarded for %s", type(key))
        except Exception:
            logger.debug("instana.span._validate_tag: ", exc_info=True)

        return (validated_key, validated_value)

    def _convert_tag_value(self, value):
        final_value = None

        try:
            final_value = repr(value)
        except Exception:
            final_value = "(non-fatal) span.set_tag: values must be one of these types: bool, float, int, list, " \
                            "set, str or alternatively support 'repr'. tag discarded"
            logger.debug(final_value, exc_info=True)
            return None
        return final_value


class SDKSpan(BaseSpan):
    ENTRY_KIND = ["entry", "server", "consumer"]
    EXIT_KIND = ["exit", "client", "producer"]

    def __init__(self, span, source, service_name, **kwargs):
        # pylint: disable=invalid-name
        super(SDKSpan, self).__init__(span, source, service_name, **kwargs)

        span_kind = self.get_span_kind(span)

        self.n = "sdk"
        self.k = span_kind[1]

        if self.k == 1 and service_name is not None:
            self.data["service"] = service_name

        self.data["sdk"]["name"] = span.operation_name
        self.data["sdk"]["type"] = span_kind[0]
        self.data["sdk"]["custom"]["tags"] = self._validate_tags(span.tags)

        if span.logs is not None and len(span.logs) > 0:
            logs = DictionaryOfStan()
            for log in span.logs:
                filtered_key_values = self._validate_tags(log.key_values)
                if len(filtered_key_values.keys()) > 0:
                    logs[repr(log.timestamp)] = filtered_key_values
            self.data["sdk"]["custom"]["logs"] = logs

        if "arguments" in span.tags:
            self.data['sdk']['arguments'] = span.tags["arguments"]

        if "return" in span.tags:
            self.data['sdk']['return'] = span.tags["return"]

        if len(span.context.baggage) > 0:
            self.data["baggage"] = span.context.baggage

    def get_span_kind(self, span):
        """
        Will retrieve the `span.kind` tag and return a tuple containing the appropriate string and integer
        values for the Instana backend

        :param span: The span to search for the `span.kind` tag
        :return: Tuple (String, Int)
        """
        kind = ("intermediate", 3)
        if "span.kind" in span.tags:
            if span.tags["span.kind"] in self.ENTRY_KIND:
                kind = ("entry", 1)
            elif span.tags["span.kind"] in self.EXIT_KIND:
                kind = ("exit", 2)
        return kind


class RegisteredSpan(BaseSpan):
    HTTP_SPANS = ("aiohttp-client", "aiohttp-server", "django", "http", "soap", "tornado-client",
                  "tornado-server", "urllib3", "wsgi")

    EXIT_SPANS = ("aiohttp-client", "boto3", "cassandra", "celery-client", "couchbase", "log", "memcache",
                  "mongo", "mysql", "postgres", "rabbitmq", "redis", "rpc-client", "sqlalchemy",
                  "soap", "tornado-client", "urllib3", "pymongo", "gcs")

    ENTRY_SPANS = ("aiohttp-server", "aws.lambda.entry", "celery-worker", "django", "wsgi", "rabbitmq",
                   "rpc-server", "tornado-server")

    LOCAL_SPANS = ("render")

    def __init__(self, span, source, service_name, **kwargs):
        # pylint: disable=invalid-name
        super(RegisteredSpan, self).__init__(span, source, service_name, **kwargs)
        self.n = span.operation_name

        self.k = 1
        if span.operation_name in self.ENTRY_SPANS:
            # entry
            self._populate_entry_span_data(span)
            self.data["service"] = service_name
        elif span.operation_name in self.EXIT_SPANS:
            self.k = 2 # exit
            self._populate_exit_span_data(span)
        elif span.operation_name in self.LOCAL_SPANS:
            self.k = 3 # intermediate span
            self._populate_local_span_data(span)

        if "rabbitmq" in self.data and self.data["rabbitmq"]["sort"] == "consume":
            self.k = 1  # entry

        # Store any leftover tags in the custom section
        if len(span.tags) > 0:
            self.data["custom"]["tags"] = self._validate_tags(span.tags)

    def _populate_entry_span_data(self, span):
        if span.operation_name in self.HTTP_SPANS:
            self._collect_http_tags(span)

        elif span.operation_name == "aws.lambda.entry":
            self.data["lambda"]["arn"] = span.tags.pop('lambda.arn', "Unknown")
            self.data["lambda"]["alias"] = None
            self.data["lambda"]["runtime"] = "python"
            self.data["lambda"]["functionName"] = span.tags.pop('lambda.name', "Unknown")
            self.data["lambda"]["functionVersion"] = span.tags.pop('lambda.version', "Unknown")
            self.data["lambda"]["trigger"] = span.tags.pop('lambda.trigger', None)
            self.data["lambda"]["error"] = None

            trigger_type = self.data["lambda"]["trigger"]

            if trigger_type in ["aws:api.gateway", "aws:application.load.balancer"]:
                self._collect_http_tags(span)
            elif trigger_type == 'aws:cloudwatch.events':
                self.data["lambda"]["cw"]["events"]["id"] = span.tags.pop('data.lambda.cw.events.id', None)
                self.data["lambda"]["cw"]["events"]["more"] = span.tags.pop('lambda.cw.events.more', False)
                self.data["lambda"]["cw"]["events"]["resources"] = span.tags.pop('lambda.cw.events.resources', None)

            elif trigger_type == 'aws:cloudwatch.logs':
                self.data["lambda"]["cw"]["logs"]["group"] = span.tags.pop('lambda.cw.logs.group', None)
                self.data["lambda"]["cw"]["logs"]["stream"] = span.tags.pop('lambda.cw.logs.stream', None)
                self.data["lambda"]["cw"]["logs"]["more"] = span.tags.pop('lambda.cw.logs.more', None)
                self.data["lambda"]["cw"]["logs"]["events"] = span.tags.pop('lambda.cw.logs.events', None)

            elif trigger_type == 'aws:s3':
                self.data["lambda"]["s3"]["events"] = span.tags.pop('lambda.s3.events', None)
            elif trigger_type == 'aws:sqs':
                self.data["lambda"]["sqs"]["messages"] = span.tags.pop('lambda.sqs.messages', None)

        elif span.operation_name == "celery-worker":
            self.data["celery"]["task"] = span.tags.pop('task', None)
            self.data["celery"]["task_id"] = span.tags.pop('task_id', None)
            self.data["celery"]["scheme"] = span.tags.pop('scheme', None)
            self.data["celery"]["host"] = span.tags.pop('host', None)
            self.data["celery"]["port"] = span.tags.pop('port', None)
            self.data["celery"]["retry-reason"] = span.tags.pop('retry-reason', None)
            self.data["celery"]["error"] = span.tags.pop('error', None)

        elif span.operation_name == "rabbitmq":
            self.data["rabbitmq"]["exchange"] = span.tags.pop('exchange', None)
            self.data["rabbitmq"]["queue"] = span.tags.pop('queue', None)
            self.data["rabbitmq"]["sort"] = span.tags.pop('sort', None)
            self.data["rabbitmq"]["address"] = span.tags.pop('address', None)
            self.data["rabbitmq"]["key"] = span.tags.pop('key', None)

        elif span.operation_name == "rpc-server":
            self.data["rpc"]["flavor"] = span.tags.pop('rpc.flavor', None)
            self.data["rpc"]["host"] = span.tags.pop('rpc.host', None)
            self.data["rpc"]["port"] = span.tags.pop('rpc.port', None)
            self.data["rpc"]["call"] = span.tags.pop('rpc.call', None)
            self.data["rpc"]["call_type"] = span.tags.pop('rpc.call_type', None)
            self.data["rpc"]["params"] = span.tags.pop('rpc.params', None)
            self.data["rpc"]["baggage"] = span.tags.pop('rpc.baggage', None)
            self.data["rpc"]["error"] = span.tags.pop('rpc.error', None)
        else:
            logger.debug("SpanRecorder: Unknown entry span: %s" % span.operation_name)

    def _populate_local_span_data(self, span):
        if span.operation_name == "render":
            self.data["render"]["name"] = span.tags.pop('name', None)
            self.data["render"]["type"] = span.tags.pop('type', None)
            self.data["log"]["message"] = span.tags.pop('message', None)
            self.data["log"]["parameters"] = span.tags.pop('parameters', None)
        else:
            logger.debug("SpanRecorder: Unknown local span: %s" % span.operation_name)

    def _populate_exit_span_data(self, span):
        if span.operation_name in self.HTTP_SPANS:
            self._collect_http_tags(span)

        elif span.operation_name == "boto3":
            # boto3 also sends http tags
            self._collect_http_tags(span)

            for tag in ['op', 'ep', 'reg', 'payload', 'error']:
                value = span.tags.pop(tag, None)
                if value is not None:
                    if tag == 'payload':
                        self.data["boto3"][tag] = self._validate_tags(value)
                    else:
                        self.data["boto3"][tag] = value

        elif span.operation_name == "cassandra":
            self.data["cassandra"]["cluster"] = span.tags.pop('cassandra.cluster', None)
            self.data["cassandra"]["query"] = span.tags.pop('cassandra.query', None)
            self.data["cassandra"]["keyspace"] = span.tags.pop('cassandra.keyspace', None)
            self.data["cassandra"]["fetchSize"] = span.tags.pop('cassandra.fetchSize', None)
            self.data["cassandra"]["achievedConsistency"] = span.tags.pop('cassandra.achievedConsistency', None)
            self.data["cassandra"]["triedHosts"] = span.tags.pop('cassandra.triedHosts', None)
            self.data["cassandra"]["fullyFetched"] = span.tags.pop('cassandra.fullyFetched', None)
            self.data["cassandra"]["error"] = span.tags.pop('cassandra.error', None)

        elif span.operation_name == "celery-client":
            self.data["celery"]["task"] = span.tags.pop('task', None)
            self.data["celery"]["task_id"] = span.tags.pop('task_id', None)
            self.data["celery"]["scheme"] = span.tags.pop('scheme', None)
            self.data["celery"]["host"] = span.tags.pop('host', None)
            self.data["celery"]["port"] = span.tags.pop('port', None)
            self.data["celery"]["error"] = span.tags.pop('error', None)

        elif span.operation_name == "couchbase":
            self.data["couchbase"]["hostname"] = span.tags.pop('couchbase.hostname', None)
            self.data["couchbase"]["bucket"] = span.tags.pop('couchbase.bucket', None)
            self.data["couchbase"]["type"] = span.tags.pop('couchbase.type', None)
            self.data["couchbase"]["error"] = span.tags.pop('couchbase.error', None)
            self.data["couchbase"]["error_type"] = span.tags.pop('couchbase.error_type', None)
            self.data["couchbase"]["sql"] = span.tags.pop('couchbase.sql', None)

        elif span.operation_name == "rabbitmq":
            self.data["rabbitmq"]["exchange"] = span.tags.pop('exchange', None)
            self.data["rabbitmq"]["queue"] = span.tags.pop('queue', None)
            self.data["rabbitmq"]["sort"] = span.tags.pop('sort', None)
            self.data["rabbitmq"]["address"] = span.tags.pop('address', None)
            self.data["rabbitmq"]["key"] = span.tags.pop('key', None)

        elif span.operation_name == "redis":
            self.data["redis"]["connection"] = span.tags.pop('connection', None)
            self.data["redis"]["driver"] = span.tags.pop('driver', None)
            self.data["redis"]["command"] = span.tags.pop('command', None)
            self.data["redis"]["error"] = span.tags.pop('redis.error', None)
            self.data["redis"]["subCommands"] = span.tags.pop('subCommands', None)

        elif span.operation_name == "rpc-client":
            self.data["rpc"]["flavor"] = span.tags.pop('rpc.flavor', None)
            self.data["rpc"]["host"] = span.tags.pop('rpc.host', None)
            self.data["rpc"]["port"] = span.tags.pop('rpc.port', None)
            self.data["rpc"]["call"] = span.tags.pop('rpc.call', None)
            self.data["rpc"]["call_type"] = span.tags.pop('rpc.call_type', None)
            self.data["rpc"]["params"] = span.tags.pop('rpc.params', None)
            self.data["rpc"]["baggage"] = span.tags.pop('rpc.baggage', None)
            self.data["rpc"]["error"] = span.tags.pop('rpc.error', None)

        elif span.operation_name == "sqlalchemy":
            self.data["sqlalchemy"]["sql"] = span.tags.pop('sqlalchemy.sql', None)
            self.data["sqlalchemy"]["eng"] = span.tags.pop('sqlalchemy.eng', None)
            self.data["sqlalchemy"]["url"] = span.tags.pop('sqlalchemy.url', None)
            self.data["sqlalchemy"]["err"] = span.tags.pop('sqlalchemy.err', None)

        elif span.operation_name == "mysql":
            self.data["mysql"]["host"] = span.tags.pop('host', None)
            self.data["mysql"]["port"] = span.tags.pop('port', None)
            self.data["mysql"]["db"] = span.tags.pop(ot_tags.DATABASE_INSTANCE, None)
            self.data["mysql"]["user"] = span.tags.pop(ot_tags.DATABASE_USER, None)
            self.data["mysql"]["stmt"] = span.tags.pop(ot_tags.DATABASE_STATEMENT, None)
            self.data["mysql"]["error"] = span.tags.pop('mysql.error', None)

        elif span.operation_name == "postgres":
            self.data["pg"]["host"] = span.tags.pop('host', None)
            self.data["pg"]["port"] = span.tags.pop('port', None)
            self.data["pg"]["db"] = span.tags.pop(ot_tags.DATABASE_INSTANCE, None)
            self.data["pg"]["user"] = span.tags.pop(ot_tags.DATABASE_USER, None)
            self.data["pg"]["stmt"] = span.tags.pop(ot_tags.DATABASE_STATEMENT, None)
            self.data["pg"]["error"] = span.tags.pop('pg.error', None)

        elif span.operation_name == "mongo":
            service = "%s:%s" % (span.tags.pop('host', None), span.tags.pop('port', None))
            namespace = "%s.%s" % (span.tags.pop('db', "?"), span.tags.pop('collection', "?"))

            self.data["mongo"]["service"] = service
            self.data["mongo"]["namespace"] = namespace
            self.data["mongo"]["command"] = span.tags.pop('command', None)
            self.data["mongo"]["filter"] = span.tags.pop('filter', None)
            self.data["mongo"]["json"] = span.tags.pop('json', None)
            self.data["mongo"]["error"] = span.tags.pop('error', None)

        elif span.operation_name == "gcs":
            self.data["gcs"]["op"] = span.tags.pop('gcs.op')
            self.data["gcs"]["bucket"] = span.tags.pop('gcs.bucket', None)
            self.data["gcs"]["object"] = span.tags.pop('gcs.object', None)
            self.data["gcs"]["entity"] = span.tags.pop('gcs.entity', None)
            self.data["gcs"]["range"] = span.tags.pop('gcs.range', None)
            self.data["gcs"]["sourceBucket"] = span.tags.pop('gcs.sourceBucket', None)
            self.data["gcs"]["sourceObject"] = span.tags.pop('gcs.sourceObject', None)
            self.data["gcs"]["sourceObjects"] = span.tags.pop('gcs.sourceObjects', None)
            self.data["gcs"]["destinationBucket"] = span.tags.pop('gcs.destinationBucket', None)
            self.data["gcs"]["destinationObject"] = span.tags.pop('gcs.destinationObject', None)
            self.data["gcs"]["numberOfOperations"] = span.tags.pop('gcs.numberOfOperations', None)
            self.data["gcs"]["projectId"] = span.tags.pop('gcs.projectId', None)
            self.data["gcs"]["accessId"] = span.tags.pop('gcs.accessId', None)

        elif span.operation_name == "log":
            # use last special key values
            for l in span.logs:
                if "message" in l.key_values:
                    self.data["log"]["message"] = l.key_values.pop("message", None)
                if "parameters" in l.key_values:
                    self.data["log"]["parameters"] = l.key_values.pop("parameters", None)
        else:
            logger.debug("SpanRecorder: Unknown exit span: %s" % span.operation_name)

    def _collect_http_tags(self, span):
        self.data["http"]["host"] = span.tags.pop("http.host", None)
        self.data["http"]["url"] = span.tags.pop(ot_tags.HTTP_URL, None)
        self.data["http"]["path"] = span.tags.pop("http.path", None)
        self.data["http"]["params"] = span.tags.pop('http.params', None)
        self.data["http"]["method"] = span.tags.pop(ot_tags.HTTP_METHOD, None)
        self.data["http"]["status"] = span.tags.pop(ot_tags.HTTP_STATUS_CODE, None)
        self.data["http"]["path_tpl"] = span.tags.pop("http.path_tpl", None)
        self.data["http"]["error"] = span.tags.pop('http.error', None)

        if span.operation_name == "soap":
            self.data["soap"]["action"] = span.tags.pop('soap.action', None)
