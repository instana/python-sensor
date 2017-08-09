import opentracing as ot
from instana import tracer, options
import logging
import os


def hook(module):
    """ Hook method to install the Instana middleware into Flask """
    if os.environ["AUTOWRAPT_BOOTSTRAP"] == "runtime":
        if "INSTANA_DEV" in os.environ:
            print("==========================================================")
            print("Instana: Running runtime hook")
            print("==========================================================")
            level = logging.DEBUG
        else:
            level = logging.WARN

        opts = options.Options(log_level=level)
        ot.global_tracer = tracer.InstanaTracer(opts)
