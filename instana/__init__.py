"""
Instana sensor and tracer. It consists of two modules that can be used as entry points:

- sensor: activates the meter to collect and transmit all kind of built-in metrics
- tracer: OpenTracing tracer implementation. It implicitly activates the meter
"""

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2017 Instana Inc.'
__credits__ = ['Pavlo Baron', 'Peter Giacomo Lombardo']
__license__ = 'MIT'
__version__ = '0.6.7'
__maintainer__ = 'Peter Giacomo Lombardo'
__email__ = 'peter.lombardo@instana.com'

__all__ = ['sensor', 'tracer']
