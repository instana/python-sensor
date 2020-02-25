"""
This file contains a config object that will hold configuration options for the package.
Defaults are set and can be overridden after package load.
"""
from __future__ import absolute_import
from .util import stan_dictionary

# La Protagonista
config = stan_dictionary()


# This option determines if tasks created via asyncio (with ensure_future or create_task) will
# automatically carry existing context into the created task.
config['asyncio_task_context_propagation']['enabled'] = False




