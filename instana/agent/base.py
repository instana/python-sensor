import requests


class BaseAgent(object):
    """ Base class for all agent flavors """
    client = None
    sensor = None
    options = None

    def __init__(self):
        self.client = requests.Session()

