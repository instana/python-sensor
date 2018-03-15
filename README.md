<div align="center">
<img src="https://disznc.s3.amazonaws.com/Python-1-2017-06-29-at-22.34.00.png"/>
</div>

# Instana

The instana package provides Python metrics and traces (request, queue & cross-host) for [Instana](https://www.instana.com/).

[![Build Status](https://travis-ci.org/instana/python-sensor.svg?branch=master)](https://travis-ci.org/instana/python-sensor)
[![OpenTracing Badge](https://img.shields.io/badge/OpenTracing-enabled-blue.svg)](http://opentracing.io)

## Note

This package supports Python 2.7 or greater.

Any and all feedback is welcome.  Happy Python visibility.

## Installation

`pip install instana` into the virtual-env or container ([hosted on pypi](https://pypi.python.org/pypi/instana))

## Django

For Django versions >= 1.10 set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=django`

For Django version 1.9.x, instead set:

  `export AUTOWRAPT_BOOTSTRAP=django19`

## Flask

To enable the Flask instrumentation, set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=flask`
  
## WSGI Compliant Stacks

The Instana sensor bundles with it WSGI middleware.  The usage of this middleware is automated for various frameworks but for those that arent' supported yet, see the [WSGI documentation](WSGI.md) for details on how to manually add it to your stack.

## Runtime Monitoring Only

_Note: When the Django or Flask instrumentation is used, runtime monitoring is automatically included.  Use this section if you only want to see runtime metrics._

To enable runtime monitoring (without request tracing), set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=runtime`

## uWSGI

### Threads

This Python instrumentation spawns a lightweight background thread to periodically collect and report process metrics.  By default, the GIL and threading is disabled under uWSGI.  If you wish to instrument your application running under uWSGI, make sure that you enable threads by passing `--enable-threads`  (or `enable-threads = true` in ini style).  More details in the [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html#a-note-on-python-threads).

### Forking off Workers

If you use uWSGI in forking workers mode, you must specify `--lazy-apps` (or `lazy-apps = true` in ini style) to load the application in the worker instead of the master process.

### uWSGI Example: Command-line

```sh
uwsgi --socket 0.0.0.0:5000 --protocol=http -w wsgi -p 4 --enable-threads --lazy-apps
```

### uWSGI Example: ini file

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

## Usage

The instana package will automatically collect key metrics from your Python processes.  Just install and go.

## Want End User Monitoring?

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

## OpenTracing

This Python package supports [OpenTracing](http://opentracing.io/).  When using this package, the OpenTracing tracer (`opentracing.tracer`) is automatically set to the `InstanaTracer`.

```Python
import opentracing

parent_span = opentracing.tracer.start_span(operation_name="asteroid")
# ... work
child_span = opentracing.tracer.start_span(operation_name="spacedust", child_of=parent_span)
child_span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
# ... work
child_span.finish()
# ... work
parent_span.finish()
```

Note: The Instana sensor has automatic instrumentation that activates at runtime.  If you need to get the current tracing context from existing instrumentation, you can use `opentracing.tracer.current_context()` and pass that return value as `childof`:

        context = opentracing.tracer.current_context()
        span = opentracing.tracer.start_span("my_span", child_of=context)

Also note that under evented systems such as gevent, concurrence and/or greenlets (which aren't supportet yet), the value `opentracing.tracer.current_context()` is likely to be inconsistent.

## Configuration

See [Configuration.md](https://github.com/instana/python-sensor/blob/master/Configuration.md)


## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal](https://docs.instana.io/ecosystem/python/).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Nodejs](https://github.com/instana/nodejs-sensor), [Go](https://github.com/instana/golang-sensor), [Ruby](https://github.com/instana/ruby-sensor) instrumentation or [many other supported technologies](https://www.instana.com/supported-technologies/).
