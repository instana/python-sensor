HTTP_CLIENT = "g.hc"
HTTP_SERVER = "g.http"


class HttpData(object):
    host = None
    url = None
    status = 0
    method = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
