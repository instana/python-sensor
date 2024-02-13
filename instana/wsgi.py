# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2017


from .instrumentation.wsgi import InstanaWSGIMiddleware

# Alias for historical name
iWSGIMiddleware = InstanaWSGIMiddleware
