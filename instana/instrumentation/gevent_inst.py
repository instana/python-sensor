from __future__ import absolute_import

import sys
from ..log import logger
from ..singletons import agent, tracer

try:
    if 'gevent' in sys.modules:
        logger.debug("Instrumenting gevent")

        import gevent
        from opentracing.scope_managers.gevent import GeventScopeManager

        def spawn_callback(gr):
            current_greenlet = gevent.getcurrent()
            parent_scope = tracer.scope_manager.active

            # logger.debug("current_greenlet: %s", current_greenlet)
            # logger.debug("other greenlet: %s", gr)

            if (type(current_greenlet) is gevent._greenlet.Greenlet) and parent_scope is not None:
                parent_scope._finish_on_close = False
                tracer._scope_manager._set_greenlet_scope(parent_scope, gr)

        logger.debug(" -> Updating tracer to use gevent based context management")
        tracer._scope_manager = GeventScopeManager()
        gevent.Greenlet.add_spawn_callback(spawn_callback)
except ImportError:
    pass
