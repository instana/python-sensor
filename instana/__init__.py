"""
Instana sensor and tracer. It consists of two modules that can be used as entry points:

- sensor: activates the meter to collect and transmit all kind of built-in metrics
- tracer: OpenTracing tracer implementation. It implicitly activates the meter
"""

__author__ = 'Instana Inc.'
__copyright__ = 'Copyright 2016 Instana Inc.'
__credits__ = ['Pavlo Baron']
__license__ = 'MIT'
__version__ = '0.0.1'
__maintainer__ = 'Pavlo Baron'
__email__ = 'pavlo.baron@instana.com'

__all__ = ['sensor', 'tracer']
