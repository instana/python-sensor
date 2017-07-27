from instana import wsgi
from flask.cli import ScriptInfo


def wrap_load_app(func):
    def wrapper(self, *args):
        app = func(self, *args)
        app.wsgi_app = wsgi.iWSGIMiddleware(app.wsgi_app)
        return app
    return wrapper


def hook(module):
    """ Hook method to install the Instana middleware into Flask """
    ScriptInfo.load_app = wrap_load_app(ScriptInfo.load_app)
