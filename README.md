# Instana

The `instana` Python package collects key metrics and distributed traces for [Instana].

Any feedback is welcome.  Happy Python visibility.

[![CircleCI](https://circleci.com/gh/instana/python-sensor/tree/main.svg?style=svg)](https://circleci.com/gh/instana/python-sensor/tree/main)
[![OpenTracing Badge](https://img.shields.io/badge/OpenTracing-disabled-red.svg)](http://opentracing.io)
[![OpenTelemetry Badge](https://img.shields.io/badge/OpenTelemetry-enabled-blue.svg)](http://opentelemetry.io)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/instana)
![GitHub Release](https://img.shields.io/github/v/release/instana/python-sensor)

> [!NOTE]
> Support for OpenTracing is deprecated starting on version 3.0.0. If you still want to use it, rely on any version earlier than 3.0.0 or use the `legacy_2.x` branch.

## Installation

Instana remotely instruments your Python web servers automatically via [Instana AutoTrace™️]. To configure which Python processes this applies to, see the [configuration page].

##  Manual Installation

If you wish to instrument your applications manually, you can install the package with the following into the `virtualenv`, `pipenv`, or container (hosted on [PyPI]):

    pip install instana

or to alternatively update an existing installation:

    pip install -U instana

### Activating Without Code Changes

The Instana package can then be activated _without any code changes required_ by setting the following environment variable for your Python application:

    export AUTOWRAPT_BOOTSTRAP=instana

This will cause the Instana Python package to instrument your Python application automatically. Once it finds the Instana host agent, it will report Python metrics and distributed traces.

### Activating via Import

Alternatively, if you prefer the manual method, import the `instana` package inside of your Python application:

    import instana

See also our detailed [installation document] for additional information covering Django, Flask, End-user Monitoring (EUM), and more.

## Documentation

You can find more documentation covering supported components and minimum versions in the Instana [documentation portal].

## Contributing

Bug reports and pull requests are welcome on GitHub at https://github.com/instana/python-sensor.

## More

Want to instrument other languages?  See our [Node.js], [Go], [Ruby] instrumentation or many other [supported technologies].

<!-- Reference links -->
[Instana]: https://www.instana.com/ "IBM Instana Observability"
[Instana AutoTrace™️]: https://www.ibm.com/docs/en/instana-observability/current?topic=kubernetes-instana-autotrace-webhook "Instana AutoTrace"
[configuration page]: https://www.ibm.com/docs/en/instana-observability/current?topic=package-python-configuration-configuring-instana#general "Instana Python package configuration"
[PyPI]: https://pypi.python.org/pypi/instana "Instana package at PyPI"
[installation document]: https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-python-instana-python-package#installation-methods "Instana Python package installation methods"
[documentation portal]: https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-python-instana-python-package "Instana Python package documentation"
[Node.js]: https://github.com/instana/nodejs "Instana Node.JS Tracer"
[Go]: https://github.com/instana/golang-sensor "Instana Go Tracer"
[Ruby]: https://github.com/instana/ruby-sensor "Instana Ruby Tracer"
[supported technologies]: https://www.instana.com/supported-technologies/ "Instana supported technologies"
