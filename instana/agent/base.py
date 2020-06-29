import requests


class BaseAgent(object):
    """ Base class for all agent flavors """
    client = None
    sensor = None
    secrets_matcher = 'contains-ignore-case'
    secrets_list = ['key', 'pass', 'secret']
    extra_headers = None
    options = None

    def __init__(self):
        self.client = requests.Session()

