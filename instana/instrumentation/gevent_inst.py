"""
Instrumentation for the gevent package.
"""
from __future__ import absolute_import

import sys
from ..log import logger
from ..singletons import tracer


def instrument_gevent():
    """ Adds context propagation to gevent greenlet spawning """
    try:
        logger.debug("Instrumenting gevent")

        import gevent
        from opentracing.scope_managers.gevent import GeventScopeManager
        from opentracing.scope_managers.gevent import _GeventScope

        def spawn_callback(new_greenlet):
            """ Handles context propagation for newly spawning greenlets """
            parent_scope = tracer.scope_manager.active
            if parent_scope is not None:
                # New greenlet, new clean slate.  Clone and make active in this new greenlet
                # the currently active scope (but don't finish() the span on close - it's a
                # clone/not the original and we don't want to close it prematurely)
                # TODO: Change to our own ScopeManagers
                parent_scope_clone = _GeventScope(parent_scope.manager, parent_scope.span, finish_on_close=False)
                tracer._scope_manager._set_greenlet_scope(parent_scope_clone, new_greenlet)

        logger.debug(" -> Updating tracer to use gevent based context management")
        tracer._scope_manager = GeventScopeManager()
        gevent.Greenlet.add_spawn_callback(spawn_callback)
    except:
        logger.debug("instrument_gevent: ", exc_info=True)


if 'gevent' in sys.modules:
    if sys.modules['gevent'].version_info < (1, 4):
        logger.debug("gevent < 1.4 detected.  The Instana package supports gevent versions 1.4 and greater.")
    else:
        instrument_gevent()
else:
    logger.debug("Instrumenting gevent: gevent not detected or loaded.  Nothing done.")
