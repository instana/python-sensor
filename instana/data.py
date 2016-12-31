class Data(object):
    http = None
    service = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
