class JsonSpan(object):
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

    def __init__(self, **kwds):
        for key in kwds:
            self.__dict__[key] = kwds[key]


class CustomData(object):
    tags = None
    logs = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class Data(object):
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

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class HttpData(object):
    host = None
    url = None
    params = None
    status = 0
    method = None
    path_tpl = None
    error = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class MySQLData(object):
    db = None
    host = None
    user = None
    stmt = None
    error = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class RabbitmqData(object):
    exchange = None
    queue = None
    sort = None
    address = None
    key = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class RedisData(object):
    connection = None
    driver = None
    command = None
    error = None
    subCommands = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class RPCData(object):
    flavor = None
    host = None
    port = None
    call = None
    call_type = None
    params = None
    baggage = None
    error = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class SQLAlchemyData(object):
    sql = None
    url = None
    eng = None
    error = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class SoapData(object):
    action = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class SDKData(object):
    name = None

    # Since 'type' and 'return' are a Python builtin and a reserved keyword respectively, these keys (all keys) are
    # lower-case'd in json encoding.  See Agent.to_json
    Type = None
    Return = None

    arguments = None
    custom = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
