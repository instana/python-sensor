class CustomData(object):
    tags = None
    logs = None

    def __init__(self, **kwds):
        self.__dict__.update(kwds)
