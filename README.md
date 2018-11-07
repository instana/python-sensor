<div align="center">
<img src="https://disznc.s3.amazonaws.com/Python-1-2017-06-29-at-22.34.00.png"/>
</div>

# Instana

The `instana` Python package collects key metrics and distributed traces for [Instana](https://www.instana.com/).

This package supports Python 2.7 or greater.

Any and all feedback is welcome.  Happy Python visibility.

[![Build Status](https://travis-ci.org/instana/python-sensor.svg?branch=master)](https://travis-ci.org/instana/python-sensor)
[![OpenTracing Badge](https://img.shields.io/badge/OpenTracing-enabled-blue.svg)](http://opentracing.io)

## Installation

None

_Instana remotely instruments your Python web servers automatically. To configure which Python processes this applies to, see the [Configuration page](https://docs.instana.io/ecosystem/python/configuration/#general)._

##  Manual Installation

If you wish to manually instrument your applications you can install the package with the following into the virtualenv, pipenv or container ([hosted on pypi](https://pypi.python.org/pypi/instana)):

    pip install instana

or to alternatively update an existing installation:

    pip install -U instana

### Activating Without Code Changes

The Instana package can then be activated _without any code changes required_ by setting the following environment variable for your Python application:

    export AUTOWRAPT_BOOTSTRAP=instana

This will cause the Instana Python package to automatically instrument your Python application.  Once it finds the Instana host agent, it will begin to report Python metrics and distributed traces.

### Activating via Import

Alternatively, if you prefer the really manual method, simply import the `instana` package inside of your Python application:

    import instana

See also our detailed [Installation document](https://docs.instana.io/ecosystem/python/installation) for additional information covering Django, Flask, End-user Monitoring (EUM) and more.

## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal](https://docs.instana.io/ecosystem/python/).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Nodejs](https://github.com/instana/nodejs-sensor), [Go](https://github.com/instana/golang-sensor), [Ruby](https://github.com/instana/ruby-sensor) instrumentation or [many other supported technologies](https://www.instana.com/supported-technologies/).
