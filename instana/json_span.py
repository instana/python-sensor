
class BaseSpan(object):
    def __str__(self):
        return self.__class__.__str__() + ": " + self.__dict__.__str__()

    def __repr__(self):
        return self.__dict__.__str__()

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class JsonSpan(BaseSpan):
    k = None
    t = 0
    p = None
    s = 0
    ts = 0
    ta = "py"
    d = 0
    n = None
    f = None
    ec = None
    error = None
    data = None
    stack = None


class CustomData(BaseSpan):
    tags = None
    logs = None


class Data(BaseSpan):
    baggage = None
    custom = None
    http = None
    rabbitmq = None
    redis = None
    rpc = None
    sdk = None
    service = None
    sqlalchemy = None
    soap = None
    log = None


class HttpData(BaseSpan):
    host = None
    url = None
    params = None
    status = 0
    method = None
    path = None
    path_tpl = None
    error = None


class MySQLData(BaseSpan):
    db = None
    host = None
    user = None
    stmt = None
    error = None


class RabbitmqData(BaseSpan):
    exchange = None
    queue = None
    sort = None
    address = None
    key = None


class RedisData(BaseSpan):
    connection = None
    driver = None
    command = None
    error = None
    subCommands = None


class RPCData(BaseSpan):
    flavor = None
    host = None
    port = None
    call = None
    call_type = None
    params = None
    baggage = None
    error = None


class SQLAlchemyData(BaseSpan):
    sql = None
    url = None
    eng = None
    error = None


class SoapData(BaseSpan):
    action = None


class SDKData(BaseSpan):
    name = None

    # Since 'type' and 'return' are a Python builtin and a reserved keyword respectively, these keys (all keys) are
    # lower-case'd in json encoding.  See Agent.to_json
    Type = None
    Return = None

    arguments = None
    custom = None

