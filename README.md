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

## uWSGI

### Threads

This Python instrumentation spawns a lightweight background thread to periodically collect and report process metrics.  By default, the GIL and threading is disabled under uWSGI.  If you wish to instrument your application running under uWSGI, make sure that you enable threads by passing `--enable-threads`  (or `enable-threads = true` in ini style).  More details in the [uWSGI documentation](https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html#a-note-on-python-threads).

### Forking off Workers

If you use uWSGI in forking workers mode, you must specify `--lazy-apps` (or `lazy-apps = true` in ini style) to load the application in the worker instead of the master process.

## Usage

The instana package will automatically collect key metrics from your Python processes.  Just install and go.

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

## Configuration

See [Configuration.md](https://github.com/instana/python-sensor/blob/master/Configuration.md)


## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal](https://docs.instana.io/ecosystem/python/).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Nodejs](https://github.com/instana/nodejs-sensor), [Go](https://github.com/instana/golang-sensor), [Ruby](https://github.com/instana/ruby-sensor) instrumentation or [many other supported technologies](https://www.instana.com/supported-technologies/).
