# (c) Copyright IBM Corp. 2021
# (c) Copyright Instana Inc. 2021


from sanic.response import text
from sanic.views import HTTPMethodView


class NameView(HTTPMethodView):
    def get(self, request, name):
        return text("Hello {}".format(name))
