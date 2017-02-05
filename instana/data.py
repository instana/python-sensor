class Data(object):
    service = None
    http = None
    baggage = None
    custom = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
