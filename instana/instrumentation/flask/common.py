from __future__ import absolute_import

import wrapt

from ...singletons import tracer


@wrapt.patch_function_wrapper('flask', 'templating._render')
def render_with_instana(wrapped, instance, argv, kwargs):
    ctx = argv[1]

    # If we're not tracing, just return
    if not hasattr(ctx['g'], 'scope'):
        return wrapped(*argv, **kwargs)

    with tracer.start_active_span("render", child_of=ctx['g'].scope.span) as rscope:
        try:
            template = argv[0]

            rscope.span.set_tag("type", "template")
            if template.name is None:
                rscope.span.set_tag("name", '(from string)')
            else:
                rscope.span.set_tag("name", template.name)

            return wrapped(*argv, **kwargs)
        except Exception as e:
            rscope.span.log_exception(e)
            raise
