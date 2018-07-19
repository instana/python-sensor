class JsonSpan(object):
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

    def __init__(self, **kwds):
        for key in kwds:
            self.__dict__[key] = kwds[key]


class Data(object):
    service = None
    http = None
    baggage = None
    custom = None
    sdk = None
    soap = None

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


class HttpData(object):
    host = None
    url = None
    status = 0
    method = None
    error = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class SoapData(object):
    action = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class CustomData(object):
    tags = None
    logs = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


class SDKData(object):
    name = None
    Type = None
    arguments = None
    Return = None
    custom = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
