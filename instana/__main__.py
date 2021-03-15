# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2019

"""
This module provides "python -m instana" functionality.  This is used for basic module
information display and a IPython console to diagnose environments.

The console is disabled by default unless the ipython package is installed.
"""
import os
import sys

print("""\
============================================================================
8888888 888b    888  .d8888b. 88888888888     d8888 888b    888        d8888
  888   8888b   888 d88P  Y88b    888        d88888 8888b   888       d88888
  888   88888b  888 Y88b.         888       d88P888 88888b  888      d88P888
  888   888Y88b 888  "Y888b.      888      d88P 888 888Y88b 888     d88P 888
  888   888 Y88b888     "Y88b.    888     d88P  888 888 Y88b888    d88P  888
  888   888  Y88888       "888    888    d88P   888 888  Y88888   d88P   888
  888   888   Y8888 Y88b  d88P    888   d8888888888 888   Y8888  d8888888888
8888888 888    Y888  "Y8888P"     888  d88P     888 888    Y888 d88P     888
============================================================================
""")

if "console" in sys.argv:
    try:
        import IPython
    except ImportError:
        print("This console is not enabled by default.")
        print("IPython not installed.  To use this debug console do: 'pip install ipython'\n")
    else:
        print("Welcome to the Instana console.\n")
        print("This is a simple IPython console with the Instana Python Sensor pre-loaded.\n")

        if "INSTANA_DEBUG" not in os.environ:
            print("If you want debug output of this sensors' activity run instead:\n")
            print("   INSTANA_DEBUG=true python -m instana console")

        print("""
Helpful Links
============================================================================

Monitoring Python Documentation:
https://www.instana.com/docs/ecosystem/python/


Help & Support:
https://support.instana.com/
""")

        IPython.start_ipython(argv=[])
else:
    print("""\
This is an informational screen for Instana.

Supported commands:
 - console: 
   * Requires ipython package: pip install ipython
   * Example: 
     - python -m instana console

See the Instana Python documentation for details on using this package with
your Python applications, workers, queues, neural networks and more.


Related Blog Posts:
============================================================================

Monitoring Python with Instana
https://www.instana.com/blog/monitoring-python-instana/

Zero-Effort, Fully Automatic Distributed Tracing for Python
https://www.instana.com/blog/zero-effort-fully-automatic-distributed-tracing-for-python/


Helpful Links
============================================================================

Monitoring Python Documentation:
https://www.instana.com/docs/ecosystem/python/

Help & Support:
https://support.instana.com/

Python Instrumentation on Github:
https://github.com/instana/python-sensor/
""")
