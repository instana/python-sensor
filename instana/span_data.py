HTTP_CLIENT = "g.hc"
HTTP_SERVER = "g.http"

class Data(object):
    service = None
    http = None
    baggage = None
    custom = None
    sdk = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class HttpData(object):
    host = None
    url = None
    status = 0
    method = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)

class CustomData(object):
    tags = None
    logs = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
