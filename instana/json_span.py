import os
import opentracing.ext.tags as ot_tags


class BaseSpan(object):
    def __str__(self):
        return "BaseSpan(%s)" % self.__dict__.__str__()

    def __repr__(self):
        return self.__dict__.__str__()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class JsonSpan(BaseSpan):
    def __init__(self, span, kind, data, agent, **kwargs):
        self.k = kind
        self.t = span.context.trace_id
        self.p = span.parent_id
        self.s = span.context.span_id
        self.ts = int(round(span.start_time * 1000))
        self.d = int(round(span.duration * 1000))
        self.f = agent.get_from_structure()
        self.ec = span.tags.pop("ec", None)
        self.error = span.tags.pop("error", None)

        if data.sdk:
            self.n = "sdk"
        else:
            self.n = span.operation_name

        if span.stack:
            self.stack = span.stack

        if len(span.context.baggage) > 0:
            data.baggage = span.context.baggage

        # Send along any left over custom tags
        if len(span.tags) > 0:
            if data.custom is None:
                data.custom = CustomData()
            data.custom.tags = span.tags

        logs = span.collect_logs()
        if len(logs) > 0:
            if data.custom is None:
                data.custom = CustomData()
            data.custom.logs = logs

        self.data = data
        super(JsonSpan, self).__init__(**kwargs)


class CustomData(BaseSpan):
    tags = None
    logs = None

    def __init__(self, **kwargs):
        super(CustomData, self).__init__(**kwargs)


class Data(BaseSpan):
    baggage = None
    cassandra = None
    couchbase = None
    custom = None
    http = None
    _lambda = None
    log = None
    pg = None
    rabbitmq = None
    redis = None
    rpc = None
    render = None
    sdk = None
    service = None
    sqlalchemy = None
    soap = None


""" General Spans """


class HttpData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.host = span.tags.pop("http.host", None)
        self.url = span.tags.pop(ot_tags.HTTP_URL, None)
        self.path = span.tags.pop("http.path", None)
        self.params = span.tags.pop('http.params', None)
        self.method = span.tags.pop(ot_tags.HTTP_METHOD, None)
        self.status = span.tags.pop(ot_tags.HTTP_STATUS_CODE, None)
        self.path_tpl = span.tags.pop("http.path_tpl", None)
        self.error = span.tags.pop('http.error', None)
        super(HttpData, self).__init__(**kwargs)


class SDKData(BaseSpan):
    name = None

    # Since 'type' and 'return' are a Python builtin and a reserved keyword respectively, these keys (all keys) are
    # lower-case'd in json encoding.  See Agent.to_json
    Type = None
    Return = None

    arguments = None
    custom = None


""" Entry Spans """


class AWSLambdaData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.arn = span.tags.pop('lambda.arn', "Unknown")
        self.alias = None
        self.runtime = "python"
        self.functionName = span.tags.pop('lambda.name', "Unknown")
        self.functionVersion = span.tags.pop('lambda.version', "Unknown")
        self.error = ""
        super(AWSLambdaData, self).__init__(**kwargs)


""" Local Spans """


class RenderData(BaseSpan):
    type = None
    name = None
    message = None
    parameters = None

    def __init__(self, span, **kwargs):
        self.name = span.tags.pop('name', None)
        self.type = span.tags.pop('type', None)
        super(RenderData, self).__init__(**kwargs)


""" Exit Spans """


class CassandraData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.cluster = span.tags.pop('cassandra.cluster', None)
        self.query = span.tags.pop('cassandra.query', None)
        self.keyspace = span.tags.pop('cassandra.keyspace', None)
        self.fetchSize = span.tags.pop('cassandra.fetchSize', None)
        self.achievedConsistency = span.tags.pop('cassandra.achievedConsistency', None)
        self.triedHosts = span.tags.pop('cassandra.triedHosts', None)
        self.fullyFetched = span.tags.pop('cassandra.fullyFetched', None)
        self.error = span.tags.pop('cassandra.error', None)
        super(CassandraData, self).__init__(**kwargs)


class CouchbaseData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.hostname = span.tags.pop('couchbase.hostname', None)
        self.bucket = span.tags.pop('couchbase.bucket', None)
        self.type = span.tags.pop('couchbase.type', None)
        self.error = span.tags.pop('couchbase.error', None)
        self.error_type = span.tags.pop('couchbase.error_type', None)
        self.sql = span.tags.pop('couchbase.sql', None)
        super(CouchbaseData, self).__init__(**kwargs)


class LogData(object):
    def __init__(self, span, **kwargs):
        self.message = span.tags.pop('message', None),
        self.parameters = span.tags.pop('parameters', None)
        super(LogData, self).__init__(**kwargs)


class MongoDBData(BaseSpan):
    def __init__(self, span, **kwargs):
        service = "%s:%s" % (span.tags.pop('host', None), span.tags.pop('port', None))
        namespace = "%s.%s" % (span.tags.pop('db', "?"), span.tags.pop('collection', "?"))

        self.service = service
        self.namespace = namespace
        self.command = span.tags.pop('command', None)
        self.filter = span.tags.pop('filter', None)
        self.json = span.tags.pop('json', None)
        self.error = span.tags.pop('command', None)
        super(MongoDBData, self).__init__(**kwargs)


class MySQLData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.host = span.tags.pop('host', None)
        self.port = span.tags.pop('port', None)
        self.db = span.tags.pop(ot_tags.DATABASE_INSTANCE, None)
        self.user = span.tags.pop(ot_tags.DATABASE_USER, None)
        self.stmt = span.tags.pop(ot_tags.DATABASE_STATEMENT, None)
        self.error = span.tags.pop('error', None)
        super(MySQLData, self).__init__(**kwargs)


class PostgresData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.host = span.tags.pop('host', None)
        self.port = span.tags.pop('port', None)
        self.db = span.tags.pop(ot_tags.DATABASE_INSTANCE, None)
        self.user = span.tags.pop(ot_tags.DATABASE_USER, None)
        self.stmt = span.tags.pop(ot_tags.DATABASE_STATEMENT, None)
        self.error = span.tags.pop('pg.error', None)
        super(PostgresData, self).__init__(**kwargs)


class RabbitmqData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.exchange = span.tags.pop('exchange', None),
        self.queue = span.tags.pop('queue', None),
        self.sort = span.tags.pop('sort', None),
        self.address = span.tags.pop('address', None),
        self.key = span.tags.pop('key', None)
        super(RabbitmqData, self).__init__(**kwargs)


class RedisData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.connection = span.tags.pop('connection', None)
        self.driver = span.tags.pop('driver', None)
        self.command = span.tags.pop('command', None)
        self.error = span.tags.pop('redis.error', None)
        self.subCommands = span.tags.pop('subCommands', None)
        super(RedisData, self).__init__(**kwargs)


class RPCData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.flavor = span.tags.pop('rpc.flavor', None)
        self.host = span.tags.pop('rpc.host', None)
        self.port = span.tags.pop('rpc.port', None)
        self.call = span.tags.pop('rpc.call', None)
        self.call_type = span.tags.pop('rpc.call_type', None)
        self.params = span.tags.pop('rpc.params', None)
        self.baggage = span.tags.pop('rpc.baggage', None)
        self.error = span.tags.pop('rpc.error', None)
        super(RPCData, self).__init__(**kwargs)


class SQLAlchemyData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.sql = span.tags.pop('sqlalchemy.sql', None)
        self.eng = span.tags.pop('sqlalchemy.eng', None)
        self.url = span.tags.pop('sqlalchemy.url', None)
        self.err = span.tags.pop('sqlalchemy.err', None)
        super(SQLAlchemyData, self).__init__(**kwargs)


class SoapData(BaseSpan):
    def __init__(self, span, **kwargs):
        self.action = span.tags.pop('soap.action', None)
        super(SoapData, self).__init__(**kwargs)

