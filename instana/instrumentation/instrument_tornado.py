from __future__ import print_function

import opentracing.ext.tags as ext
import opentracing as ot
import instana
import opentracing
import wrapt

try:
	import instrument_tornado

	@wrapt.patch_function_wrapper('tornado.web', '_HandlerDelegate.execute')
	def wrapRequestHandler(wrapped, instance, args, kwargs):
		try:
			print(instance.request)
			print(args)
			span = opentracing.tracer.start_span(operation_name="tornade-request 🌪")
			span.set_tag(ext.COMPONENT, "RequestHandler")
			span.set_tag(ext.SPAN_KIND, "tornado-request-handler")
			span.set_tag(ext.SPAN_KIND, ext.SPAN_KIND_RPC_SERVER)
			span.set_tag(ext.PEER_HOSTNAME, instance.request.host)
			span.set_tag(ext.HTTP_URL, instance.request.uri)
			span.set_tag(ext.HTTP_METHOD, instance.request.method)
			rv = wrapped(*args, **kwargs)
		except Exception as e:
			span.log_kv({'message': e})
			span.set_tag("error", True)
			ec = span.tags.get('ec', 0)
			span.set_tag("ec", ec + 1)
			span.finish()
			raise
		else:
			span.set_tag(ext.HTTP_STATUS_CODE, 200)
			span.finish()
			return rv

	def __call__(self, request):
		env = request.environ
		if 'HTTP_X_INSTANA_T' in env and 'HTTP_X_INSTANA_S' in env:
			ctx = ot.global_tracer.extract(ot.Format.HTTP_HEADERS, env)
			span = ot.global_tracer.start_span("tornado", child_of=ctx)
		else:
			span = ot.global_tracer.start_span("tornado")

		span.set_tag(ext.HTTP_URL, env['PATH_INFO'])
		span.set_tag("http.params", env['QUERY_STRING'])
		span.set_tag(ext.HTTP_METHOD, request.method)
		span.set_tag("http.host", env['HTTP_HOST'])
		response = self.get_response(request)

		if 500 <= response.status_code <= 511:
			span.set_tag("error", True)
			ec = span.tags.get('ec', 0)
			span.set_tag("ec", ec + 1)

		span.set_tag(ext.HTTP_STATUS_CODE, response.status_code)
		ot.global_tracer.inject(span.context, ot.Format.HTTP_HEADERS, response)
		span.finish()
		return response

	instana.log.debug("Instrumenting tornado")

except ImportError:
	pass
