from __future__ import print_function
from __future__ import absolute_import
from .instrumentation.django import middleware
import os

def hook(module):
    """ Hook method to activate the Instana sensor """
    if os.environ["AUTOWRAPT_BOOTSTRAP"] == "runtime":
        if "INSTANA_DEV" in os.environ:
            print("==========================================================")
            print("Instana: Running runtime hook")
            print("==========================================================")
