from __future__ import absolute_import

try:
    import flask
    from flask.signals import signals_available

    # `signals_available` indicates whether the Flask process is running with or without blinker support:
    # https://pypi.org/project/blinker/
    #
    # Blinker support is preferred but we do the best we can when it's not available.
    #

    from . import common

    if signals_available is True:
        import instana.instrumentation.flask.with_blinker
    else:
        import instana.instrumentation.flask.vanilla
except ImportError:
    pass
