# Overview

Once the Instana python package is installed and available to the Python application, it can be actived via environment variable (without any code changes) or done manually.  See below for details.

To install the Python sensor:

    pip install instana

or to alternatively update an existing installation:

    pip install -U instana

# Automated

The Instana package sensor can be enabled without any code modifications.  To do this, set the following environment variable for your Python application:

    AUTOWRAPT_BOOTSTRAP=runtime

This will cause the Instana Python package to automatically instrument your Python application.  Once it finds the host agent, it will begin to report Python metrics.

# Manual

In any Python 2.7 or great application, to manually enable the Instana sensor, simply import the package:

    import instana

This will initialize the package and it will begin to report key Python metrics.

# Django (Automated)

The Instana package offers a method to automatically instrument your Django application without any code changes required.  To enable the Django instrumetation, set the environment variable `AUTOWRAPT_BOOTSTRAP=django` (use `django19` for Django version 1.9.x) for your Python application.

# Django (Manual Installation)

To instead manually install the Instana Django middleware into your Django application, import the package and add `instana.django.InstanaMiddleware` to the top of your `MIDDLEWARE` (or `MIDDLEWARE_CLASSES` for earlier versions) in your `settings.py`:

```Python
import instana

MIDDLEWARE = [
    'instana.django.InstanaMiddleware',
    # ...
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

# Flask

To enable the Flask instrumentation, set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=flask`

# WSGI Stacks

The Instana sensor bundles with it WSGI middleware.  The usage of this middleware is automated for various frameworks but for those that arent' supported yet, see the [WSGI documentation](WSGI.md) for details on how to manually add it to your stack.

# uWSGI

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
