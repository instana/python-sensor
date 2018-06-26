import opentracing as ot

from instana import options, tracer

# This file is the hook for autoinstrumenation.
# Here, we should:
#  1. Make sure instana sensor is not already active in the process
#  2. Activate properly
#    a. Runtime metrics
#    b. Detect and instrument framework
#    c. Detect and instrument any libraries

opts = options.Options()
ot.tracer = tracer.InstanaTracer(opts)
