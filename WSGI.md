The Instana sensor includes WSGI middleware that can be added to any WSGI compliant stack.  This is automated for various stacks but can also be done manually for those we haven't added support for yet.

The general usage is:

```python
import instana
from instana.wsgi import iWSGIMiddleware

# Wrap the wsgi app in Instana middleware (iWSGIMiddleware)
wsgiapp = iWSGIMiddleware(MyWSGIApplication())
```

We are working to automate this for all major frameworks but in the meantime, here are some specific quick starts for those we don't have automatic support for yet.

## CherryPy

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

`uwsgi --socket 127.0.0.1:8080 --protocol=http --wsgi-file mycherry.py --callable wsgiapp -H ~/.local/share/virtualenvs/cherrypyapp-C1BUba0z`

Where `~/.local/share/virtualenvs/cherrypyapp-C1BUba0z` is the path to my local virtualenv from pipenv
