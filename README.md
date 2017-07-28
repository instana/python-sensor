<div align="center">
<img src="https://disznc.s3.amazonaws.com/Python-1-2017-06-29-at-22.34.00.png"/>
</div>

# Instana

The instana package provides Python metrics and traces (request, queue & cross-host) for [Instana](https://www.instana.com/).

This package is currently in BETA (but maturing fast).

[![Build Status](https://travis-ci.org/instana/python-sensor.svg?branch=master)](https://travis-ci.org/instana/python-sensor)

## Note

This package supports Python 2.7 or greater.

Any and all feedback is welcome.  Happy Python visibility.

## Installation

For this BETA, we currently support tracing of Django and Flask applications or optionally just runtime monitoring of your Python applications.

`pip install instana` into the virtual-env or container ([hosted on pypi](https://pypi.python.org/pypi/instana))

## Django

For Django versions >= 1.10 set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=django`

For Django version 1.9.x, instead set:

  `export AUTOWRAPT_BOOTSTRAP=django19`

## Flask

To enable the Flask instrumentation, set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=flask`

## Runtime Monitoring Only

_Note: When the Django or Flask instrumentation is used, runtime monitoring is automatically included.  Use this section if you only want to see runtime metrics._

To enable runtime monitoring (without request tracing), set the following environment variable in your _application boot environment_ and then restart your application:

  `export AUTOWRAPT_BOOTSTRAP=runtime`

## Usage

The instana package will automatically collect key metrics from your Python processes.  Just install and go.

## Tracing

This Python package supports [OpenTracing](http://opentracing.io/).

## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal](https://instana.atlassian.net/wiki/display/DOCS/Python).

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Nodejs](https://github.com/instana/nodejs-sensor), [Go](https://github.com/instana/golang-sensor), [Ruby](https://github.com/instana/ruby-sensor) instrumentation or [many other supported technologies](https://www.instana.com/supported-technologies/).
