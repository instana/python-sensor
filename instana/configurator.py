from __future__ import absolute_import
from collections import defaultdict

# This file contains a config object that will hold configuration options for the package.
# Defaults are set and can be overridden after package load.


# Simple implementation of a nested dictionary.
#
# Same as:
#   stan_dictionary = lambda: defaultdict(stan_dictionary)
# but we use the function form because of PEP 8
#
def stan_dictionary():
    return defaultdict(stan_dictionary)


# La Protagonista
config = stan_dictionary()


# This option determines if tasks created via asyncio (with ensure_future or create_task) will
# automatically carry existing context into the created task.
config['asyncio_task_context_propagation']['enabled'] = False




