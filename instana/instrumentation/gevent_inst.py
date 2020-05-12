from __future__ import absolute_import

import sys
from ..log import logger
from ..singletons import tracer

try:
    if 'gevent' in sys.modules:
        logger.debug("Instrumenting gevent")

        import gevent
        from opentracing.scope_managers.gevent import GeventScopeManager
        from opentracing.scope_managers.gevent import _GeventScope

        def spawn_callback(gr):
            parent_scope = tracer.scope_manager.active
            if parent_scope is not None:
                # New greenlet, new clean slate.  Clone and make active in this new greenlet
                # the currently active scope (but don't close this span on close - it's a
                # clone/not the original)
                parent_scope_clone = _GeventScope(parent_scope.manager, parent_scope.span, finish_on_close=False)
                tracer._scope_manager._set_greenlet_scope(parent_scope_clone, gr)

        logger.debug(" -> Updating tracer to use gevent based context management")
        tracer._scope_manager = GeventScopeManager()
        gevent.Greenlet.add_spawn_callback(spawn_callback)
except ImportError:
    pass
