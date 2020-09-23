import re

try:
    # Python 3
    from urllib.parse import unquote
except ImportError:
    # Python 2
    from urllib import unquote

# _storage_api defines a conversion of Google Storage JSON API requests into span tags as follows:
#   request_method -> path_matcher -> collector
#
# * request method - the HTTP method used to make an API request (GET, POST, etc.)
# * path_matcher - either a string or a regex applied to the API request path (string values match first).
# * collector - a lambda returning a dict of span from  API request query string.
#               parameters and request body data. If a regex is used as a path matcher, the match result
#               will be provided as a third argument.
#
# The API documentation can be found at https://cloud.google.com/storage/docs/json_api
_storage_api = {
    'GET': {
        #####################
        # Bucket operations #
        #####################
        '/b': lambda params, data: {
            'gcs.op': 'buckets.list',
            'gcs.projectId': params.get('project', None)
        },
        re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'buckets.get',
            'gcs.bucket': unquote(match.group('bucket')),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/iam$'): lambda params, data, match: {
            'gcs.op': 'buckets.getIamPolicy',
            'gcs.bucket': unquote(match.group('bucket')),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/iam/testPermissions$'): lambda params, data, match: {
            'gcs.op': 'buckets.testIamPermissions',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        ##########################
        # Object/blob operations #
        ##########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
            'gcs.op': params.get('alt', 'json') == 'media' and 'objects.get' or 'objects.attrs',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/o$'): lambda params, data, match: {
            'gcs.op': 'objects.list',
            'gcs.bucket': unquote(match.group('bucket'))
        },

        ##################################
        # Default object ACLs operations #
        ##################################
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.get',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.entity': unquote(match.group('entity'))
        },
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.list',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        #########################
        # Object ACL operations #
        #########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.get',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
            'gcs.entity': unquote(match.group('entity'))
        },
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.list',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object'))
        },

        ########################
        # HMAC keys operations #
        ########################
        re.compile('^/projects/(?P<project>[^/]+)/hmacKeys$'): lambda params, data, match: {
            'gcs.op': 'hmacKeys.list',
            'gcs.projectId': unquote(match.group('project'))
        },
        re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'hmacKeys.get',
            'gcs.projectId': unquote(match.group('project')),
            'gcs.accessId': unquote(match.group('accessId'))
        },

        ##############################
        # Service account operations #
        ##############################
        re.compile('^/projects/(?P<project>[^/]+)/serviceAccount$'): lambda params, data, match: {
            'gcs.op': 'serviceAccount.get',
            'gcs.projectId': unquote(match.group('project'))
        }
    },
    'POST': {
        #####################
        # Bucket operations #
        #####################
        '/b': lambda params, data: {
            'gcs.op': 'buckets.insert',
            'gcs.projectId': params.get('project', None),
            'gcs.bucket': data.get('name', None),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/lockRetentionPolicy$'): lambda params, data, match: {
            'gcs.op': 'buckets.lockRetentionPolicy',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        ##########################
        # Object/blob operations #
        ##########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/compose$'): lambda params, data, match: {
            'gcs.op': 'objects.compose',
            'gcs.destinationBucket': unquote(match.group('bucket')),
            'gcs.destinationObject': unquote(match.group('object')),
            'gcs.sourceObjects': ','.join(
                ['%s/%s' % (unquote(match.group('bucket')), o['name']) for o in data.get('sourceObjects', []) if 'name' in o]
            )
        },
        re.compile('^/b/(?P<srcBucket>[^/]+)/o/(?P<srcObject>[^/]+)/copyTo/b/(?P<destBucket>[^/]+)/o/(?P<destObject>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objects.copy',
            'gcs.destinationBucket': unquote(match.group('destBucket')),
            'gcs.destinationObject': unquote(match.group('destObject')),
            'gcs.sourceBucket': unquote(match.group('srcBucket')),
            'gcs.sourceObject': unquote(match.group('srcObject')),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/o$'): lambda params, data, match: {
            'gcs.op': 'objects.insert',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': params.get('name', data.get('name', None)),
        },
        re.compile('^/b/(?P<srcBucket>[^/]+)/o/(?P<srcObject>[^/]+)/rewriteTo/b/(?P<destBucket>[^/]+)/o/(?P<destObject>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objects.rewrite',
            'gcs.destinationBucket': unquote(match.group('destBucket')),
            'gcs.destinationObject': unquote(match.group('destObject')),
            'gcs.sourceBucket': unquote(match.group('srcBucket')),
            'gcs.sourceObject': unquote(match.group('srcObject')),
        },

        ######################
        # Channel operations #
        ######################
        '/channels/stop': lambda params, data: {
            'gcs.op': 'channels.stop',
            'gcs.entity': data.get('id', None)
        },

        ##################################
        # Default object ACLs operations #
        ##################################
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.insert',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.entity': data.get('entity', None)
        },

        #########################
        # Object ACL operations #
        #########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.insert',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
            'gcs.entity': data.get('entity', None)
        },

        ########################
        # HMAC keys operations #
        ########################
        re.compile('^/projects/(?P<project>[^/]+)/hmacKeys$'): lambda params, data, match: {
            'gcs.op': 'hmacKeys.create',
            'gcs.projectId': unquote(match.group('project'))
        }
    },
    'PATCH': {
        #####################
        # Bucket operations #
        #####################
        re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'buckets.patch',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        ##########################
        # Object/blob operations #
        ##########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objects.patch',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
        },

        ##################################
        # Default object ACLs operations #
        ##################################
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.patch',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.entity': unquote(match.group('entity'))
        },

        #########################
        # Object ACL operations #
        #########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.patch',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
            'gcs.entity': unquote(match.group('entity'))
        }
    },
    'PUT': {
        #####################
        # Bucket operations #
        #####################
        re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'buckets.update',
            'gcs.bucket': unquote(match.group('bucket')),
        },
        re.compile('^/b/(?P<bucket>[^/]+)/iam$'): lambda params, data, match: {
            'gcs.op': 'buckets.setIamPolicy',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        ##########################
        # Object/blob operations #
        ##########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objects.update',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
        },

        ##################################
        # Default object ACLs operations #
        ##################################
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.update',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.entity': unquote(match.group('entity'))
        },

        #########################
        # Object ACL operations #
        #########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.update',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
            'gcs.entity': unquote(match.group('entity'))
        },

        ########################
        # HMAC keys operations #
        ########################
        re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'hmacKeys.update',
            'gcs.projectId': unquote(match.group('project')),
            'gcs.accessId': unquote(match.group('accessId'))
        }
    },
    'DELETE': {
        #####################
        # Bucket operations #
        #####################
        re.compile('^/b/(?P<bucket>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'buckets.delete',
            'gcs.bucket': unquote(match.group('bucket')),
        },

        ##########################
        # Object/blob operations #
        ##########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objects.delete',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
        },

        ##################################
        # Default object ACLs operations #
        ##################################
        re.compile('^/b/(?P<bucket>[^/]+)/defaultObjectAcl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'defaultAcls.delete',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.entity': unquote(match.group('entity'))
        },

        #########################
        # Object ACL operations #
        #########################
        re.compile('^/b/(?P<bucket>[^/]+)/o/(?P<object>[^/]+)/acl/(?P<entity>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'objectAcls.delete',
            'gcs.bucket': unquote(match.group('bucket')),
            'gcs.object': unquote(match.group('object')),
            'gcs.entity': unquote(match.group('entity'))
        },

        ########################
        # HMAC keys operations #
        ########################
        re.compile('^/projects/(?P<project>[^/]+)/hmacKeys/(?P<accessId>[^/]+)$'): lambda params, data, match: {
            'gcs.op': 'hmacKeys.delete',
            'gcs.projectId': unquote(match.group('project')),
            'gcs.accessId': unquote(match.group('accessId'))
        }
    }
}
