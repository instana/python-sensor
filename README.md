<div align="center">
<img src="https://disznc.s3.amazonaws.com/Python-1-2017-06-29-at-22.34.00.png"/>
</div>

# Instana

The instana package provides Python metrics and traces (request, queue & cross-host) for [Instana](https://www.instana.com/).

This package supports Python 2.7 or greater.

Any and all feedback is welcome.  Happy Python visibility.

[![Build Status](https://travis-ci.org/instana/python-sensor.svg?branch=master)](https://travis-ci.org/instana/python-sensor)
[![OpenTracing Badge](https://img.shields.io/badge/OpenTracing-enabled-blue.svg)](http://opentracing.io)

## Usage & Installation

The instana package will automatically collect metrics and distributed traces from your Python processes.  Just install and go.

`pip install instana` into the virtual-env or container ([hosted on pypi](https://pypi.python.org/pypi/instana))

The Instana package can then be activated _without any code changes required_ by setting the following environment variable for your Python application:

    export AUTOWRAPT_BOOTSTRAP=instana

alternatively, if you prefer the manual method, simply import the `instana` package inside of your Python application:

    import instana

See our detailed [Installation document](INSTALLATION.md) for additional information covering Django, Flask, End-user Monitoring (EUM) and more.

## OpenTracing

This Python package supports [OpenTracing](http://opentracing.io/).  When using this package, the OpenTracing tracer (`opentracing.tracer`) is automatically set to the `InstanaTracer`.

```Python
import opentracing

with opentracing.tracer.start_active_span('asteroid 💫') as pscope:
    pscope.span.set_tag(ext.COMPONENT, "Python simple example app")
    pscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
    pscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
    pscope.span.set_tag(ext.HTTP_URL, "/python/simple/one")
    pscope.span.set_tag(ext.HTTP_METHOD, "GET")
    pscope.span.set_tag(ext.HTTP_STATUS_CODE, 200)
    pscope.span.log_kv({"foo": "bar"})
    # ... work ...

    with opentracing.tracer.start_active_span('spacedust 🌚', child_of=pscope.span) as cscope:
        cscope.span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_CLIENT)
        cscope.span.set_tag(ext.PEER_HOSTNAME, "localhost")
        cscope.span.set_tag(ext.HTTP_URL, "/python/simple/two")
        cscope.span.set_tag(ext.HTTP_METHOD, "POST")
        cscope.span.set_tag(ext.HTTP_STATUS_CODE, 204)
        cscope.span.set_baggage_item("someBaggage", "someValue")
        # ... work ...
```

## Configuration

For details on how to configure the Instana Python package, see [Configuration.md](https://github.com/instana/python-sensor/blob/master/Configuration.md)

## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal](https://docs.instana.io/ecosystem/python/).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Nodejs](https://github.com/instana/nodejs-sensor), [Go](https://github.com/instana/golang-sensor), [Ruby](https://github.com/instana/ruby-sensor) instrumentation or [many other supported technologies](https://www.instana.com/supported-technologies/).
