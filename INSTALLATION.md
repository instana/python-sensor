# Overview

Once the Instana python package is installed and available to the Python application, it can be actived via environment variable (without any code changes) or done manually.  See below for details.

To install the Python sensor:

    pip install instana

or to alternatively update an existing installation:

    pip install -U instana

# Automated

The Instana package sensor can be enabled without any code modifications required.  To do this, install the package and set the following environment variable for your Python application:

    AUTOWRAPT_BOOTSTRAP=instana

This will cause the Instana Python package to automatically instrument your Python application.  Once it finds the Instana host agent, it will begin to report Python metrics.

# Manual

In any Python 2.7 or greater application, to manually enable the Instana sensor, simply import the package:

    import instana

# Flask

To enable the Flask instrumentation, set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=flask`

# Django (Manual)

When the `AUTOWRAPT_BOOTSTRAP=instana` environment variable is set, the Django framework should be automatically detected and instrumented.  If for some reason, you prefer to or need to manually instrument Django, you can instead add `instana.instrumentation.django.middleware.InstanaMiddleware` to your MIDDLEWARE list in `settings.py`:

```Python
import os
import instana

# ... <snip> ...

MIDDLEWARE = [
    'instana.instrumentation.django.middleware.InstanaMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

# WSGI Stacks

The Instana sensor includes WSGI middleware that can be added to any WSGI compliant stack.  This is automated for various stacks but can also be done manually for those we haven't added support for yet.

The general usage is:

```python
import instana
from instana.wsgi import iWSGIMiddleware

# Wrap the wsgi app in Instana middleware (iWSGIMiddleware)
wsgiapp = iWSGIMiddleware(MyWSGIApplication())
```

We are working to automate this for all major frameworks but in the meantime, here are some specific quick starts for those we don't have automatic support for yet.

## CherryPy WSGI

```python
import cherrypy
import instana
from instana.wsgi import iWSGIMiddleware

# My CherryPy application
class Root(object):
    @cherrypy.expose
    def index(self):
        return "hello world"

cherrypy.config.update({'engine.autoreload.on': False})
cherrypy.server.unsubscribe()
cherrypy.engine.start()

# Wrap the wsgi app in Instana middleware (iWSGIMiddleware)
wsgiapp = iWSGIMiddleware(cherrypy.tree.mount(Root()))
```

In this example, we use uwsgi as the webserver and booted with:

    uwsgi --socket 127.0.0.1:8080 --protocol=http --wsgi-file mycherry.py --callable wsgiapp -H ~/.local/share/virtualenvs/cherrypyapp-C1BUba0z

Where `~/.local/share/virtualenvs/cherrypyapp-C1BUba0z` is the path to my local virtualenv from pipenv

## Falcon WSGI

The Falcon framework can also be instrumented via the WSGI wrapper as such:

```python
import falcon
import instana
from instana.wsgi import iWSGIMiddleware

app = falcon.API()

# ...

app = iWSGIMiddleware(app)
```

Then booting your stack with `gunicorn myfalcon:app` as an example

## Tornado WSGI

You can have request visbility in Tornado by adding the Instana WSGI to your application:

```python
import tornado.web
import tornado.wsgi
import wsgiref.simple_server
from instana.wsgi import iWSGIMiddleware

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

if __name__ == "__main__":
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])
    wsgi_app = iWSGIMiddleware(tornado.wsgi.WSGIAdapter(application))
    server = wsgiref.simple_server.make_server('', 8888, wsgi_app)
    server.serve_forever()
```

# uWSGI Webserver

tldr; Make sure `enable-threads` and `lazy-apps` is enabled for uwsgi.

## Threads

This Python instrumentation spawns a lightweight background thread to periodically collect and report process metrics.  By default, the GIL and threading is disabled under uWSGI.  If you wish to instrument your application running under uWSGI, make sure that you enable threads by passing `--enable-threads`  (or `enable-threads = true` in ini style).  More details in the [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html#a-note-on-python-threads).

## Forking off Workers

If you use uWSGI in forking workers mode, you must specify `--lazy-apps` (or `lazy-apps = true` in ini style) to load the application in the worker instead of the master process.

## uWSGI Example: Command-line

```sh
uwsgi --socket 0.0.0.0:5000 --protocol=http -w wsgi -p 4 --enable-threads --lazy-apps
```

## uWSGI Example: ini file

```ini
[uwsgi]
http = :5000
master = true
processes = 4
enable-threads = true # required
lazy-apps = true # if using "processes", set lazy-apps to true

# Set the Instana sensor environment variable here
env = AUTOWRAPT_BOOTSTRAP=flask
```
# Want End User Monitoring?

Instana provides deep end user monitoring that links server side traces with browser events to give you a complete view from server to browser.

For Python templates and views, get your EUM API key from your Instana dashboard and you can call `instana.helpers.eum_snippet(api_key='abc')` from within your layout file.  This will output
a small javascript snippet of code to instrument browser events.  It's based on [Weasel](https://github.com/instana/weasel).  Check it out.

As an example, you could do the following:

```python
from instana.helpers import eum_snippet

instana.api_key = 'abc'
meta_kvs = { 'username': user.name }

# This will return a string containing the EUM javascript for the layout or view.
eum_snippet(meta=meta_kvs)
```

The optional second argument to `eum_snippet()` is a hash of metadata key/values that will be reported along with the browser instrumentation.

![Instana EUM example with metadata](https://s3.amazonaws.com/instana/Instana+Gameface+EUM+with+metadata+2016-12-22+at+15.32.01.png)

See also the [End User Monitoring](https://docs.instana.io/products/website_monitoring/#configuration) in the Instana documentation portal.
