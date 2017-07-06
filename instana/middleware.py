import opentracing
import instana.tracer
import opentracing.ext.tags as ext


class InstanaMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response
        opentracing.global_tracer = instana.tracer.InstanaTracer()
        self

    def __call__(self, request):
        span = opentracing.global_tracer.start_span("django")

        span.set_tag(ext.HTTP_URL, request.environ['PATH_INFO'])
        span.set_tag("http.params", request.environ['QUERY_STRING'])
        span.set_tag(ext.HTTP_METHOD, request.method)
        span.set_tag("http.host", request.environ['HTTP_HOST'])

        response = self.get_response(request)

        span.set_tag(ext.HTTP_STATUS_CODE, response.status_code)
        span.finish()
        return response
