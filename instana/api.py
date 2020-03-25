"""
This module provides a client for the Instana REST API.

Use of this client requires the URL of your Instana account dashboard
and an API token.  The API token can be generated in your dashboard under
Settings > Access Control > API Tokens.

See the associated REST API documentation here:
https://documenter.getpostman.com/view/1527374/instana-api/2TqWQh#intro

The API currently uses the requests package to make the REST calls to the API.
As such, requests response objects are returned from API calls.
"""
import os
import sys
import json
import time
import certifi
import urllib3
from .log import logger as log
from .util import package_version


PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

if PY2:
    from urllib import urlencode
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.inject_into_urllib3()
else:
    import urllib3
    from urllib.parse import urlencode


# For use with the Token related API calls
token_config = {
    "id": "",
    "name": "",
    "canConfigureServiceMapping": False,
    "canConfigureEumApplications": False,
    "canConfigureUsers": False,
    "canInstallNewAgents": False,
    "canSeeUsageInformation": False,
    "canConfigureIntegrations": False,
    "canSeeOnPremLicenseInformation": False,
    "canConfigureRoles": False,
    "canConfigureCustomAlerts": False,
    "canConfigureApiTokens": False,
    "canConfigureAgentRunMode": False,
    "canViewAuditLog": False,
    "canConfigureObjectives": False
}

# For use with the Bindings related API calls
binding_config = {
  "id": "1",
  "enabled": True,
  "triggering": False,
  "severity": 5,
  "text": "text",
  "description": "desc",
  "expirationTime": 60000,
  "query": "",
  "ruleIds": [
    "2"
  ]
}

# For use with the Rule related API calls
rule_config = {
  "id": "1",
  "name": "test rule",
  "entityType": "mariaDbDatabase",
  "metricName": "status.MAX_USED_CONNECTIONS",
  "rollup": 1000,
  "window": 60000,
  "aggregation": "avg",
  "conditionOperator": ">=",
  "conditionValue": 10
}

# For use with the Role related API calls
role_config = {
    "id": "1",
    "name": "Developer",
    "implicitViewFilter": "",
    "canConfigureServiceMapping": True,
    "canConfigureEumApplications": True,
    "canConfigureUsers": False,
    "canInstallNewAgents": False,
    "canSeeUsageInformation": False,
    "canConfigureIntegrations": False,
    "canSeeOnPremLicenseInformation": False,
    "canConfigureRoles": False,
    "canConfigureCustomAlerts": False,
    "canConfigureApiTokens": False,
    "canConfigureAgentRunMode": False,
    "canViewAuditLog": False,
    "canConfigureObjectives": False
}


class APIClient(object):
    """
    The Python client to the Instana REST API.

    This client supports the use of environment variables.  These environment variables
    will override any passed in options:

        INSTANA_API_TOKEN=asdffdsa
        INSTANA_BASE_URL=https://test-test.instana.io

    Example usage:
        from instana.api import APIClient
        c = APIClient(base_url="https://test-test.instana.io", api_token='asdffdsa')

        # Retrieve the current application view
        x = c.application_view()
        x.json()

        # Retrieve snapshots results from a query
        y = c.snapshots("entity.selfType:webService entity.service.name:\"pwpush.com\"")
    """
    base_url = None
    api_token = None

    def __init__(self, **kwds):
        for key in kwds:
            self.__dict__[key] = kwds[key]

        log.warn("APIClient: This APIClient will be removed in a future version of this package.  Please"
                 "migrate away as soon as possible.")

        if "INSTANA_API_TOKEN" in os.environ:
            self.api_token = os.environ["INSTANA_API_TOKEN"]

        if "INSTANA_BASE_URL" in os.environ:
            self.base_url = os.environ["INSTANA_BASE_URL"]

        if self.base_url is None or self.api_token is None:
            log.warn("APIClient: API token or Base URL not set.  No-op mode")
        else:
            self.api_key = "apiToken %s" % self.api_token
            self.headers = {'Authorization': self.api_key, 'User-Agent': 'instana-python-sensor v' + package_version()}
            self.http = urllib3.PoolManager(cert_reqs='CERT_REQUIRED',
                                            ca_certs=certifi.where())

    def ts_now(self):
        return int(round(time.time() * 1000))

    def build_url(self, path, query_args):
        if self.base_url and self.api_token:
            url = self.base_url + path
        else:
            url = ""

        if query_args:
            encoded_args = urlencode(query_args)
            url = url + '?' + encoded_args
        return url

    def get(self, path, query_args=None):
        if self.base_url and self.api_token:
            url = self.build_url(path, query_args)
            return self.http.request('GET', url, headers=self.headers)

    def put(self, path, query_args=None, payload=''):
        if self.base_url and self.api_token:
            url = self.build_url(path, query_args)
            encoded_data = json.dumps(payload).encode('utf-8')
            post_headers = self.headers
            post_headers['Content-Type'] = 'application/json'
            return self.http.request('PUT', url, body=encoded_data, headers=post_headers)

    def post(self, path, query_args=None, payload=''):
        if self.base_url and self.api_token:
            url = self.build_url(path, query_args)
            encoded_data = json.dumps(payload).encode('utf-8')
            post_headers = self.headers
            post_headers['Content-Type'] = 'application/json'
            return self.http.request('POST', url, body=encoded_data, headers=post_headers)

    def delete(self, path, query_args):
        if self.base_url and self.api_token:
            url = self.build_url(path, query_args)
            return self.http.request('DELETE', url, headers=self.headers)

    def tokens(self):
        return self.get('/api/apiTokens')

    def token(self, token):
        return self.get('/api/apiTokens/%s' % token)

    def delete_token(self, token):
        return self.delete('/api/apiTokens/%s' % token)

    def upsert_token(self, token_config):
        return self.put('/api/apiTokens/%s' % token_config["id"], payload=token_config)

    def audit_log(self):
        return self.get('/api/auditlog')

    def eum_apps(self):
        return self.get('/api/eumApps')

    def create_eum_app(self, name):
        return self.post('/api/eumApps', payload={'name': name})

    def rename_eum_app(self, eum_app_id, new_name):
        return self.put('/api/eumApps/%s' % (eum_app_id), payload={'name': new_name})

    def delete_eum_app(self, eum_app_id):
        return self.delete('/api/eumApps/%s' % eum_app_id)

    def events(self, window_size=300000, to=None):
        if to is None:
            to = self.ts_now()
        return self.get('/api/events/', query_args={'windowsize': window_size, 'to': to})

    def event(self, event_id):
        return self.get('/api/events/%s' % event_id)

    def metrics(self, metric_name, ts_from, ts_to, aggregation, snapshot_id, rollup):
        params = {'metric': metric_name,
                  'from': ts_from,
                  'to': ts_to,
                  'aggregation': aggregation,
                  'snapshotId': snapshot_id,
                  'rollup': rollup}
        return self.get('/api/metrics', query_args=params)

    def metric(self, metric_name, timestamp, aggregation, snapshot_id, rollup):
        params = {'metric': metric_name,
                  'time': timestamp,
                  'aggregation': aggregation,
                  'snapshotId': snapshot_id,
                  'rollup': rollup}
        return self.get('/api/metric', query_args=params)

    def rule_bindings(self):
        return self.get('/api/ruleBindings')

    def rule_binding(self, rule_binding_id):
        return self.get('/api/ruleBindings/%s' % rule_binding_id)

    def upsert_rule_binding(self, rule_binding_config):
        path = '/api/ruleBindings/%s' % rule_binding_config["id"]
        return self.put(path, rule_binding_config)

    def delete_rule_binding(self, rule_binding_id):
        return self.delete('/api/ruleBindings/%s' % rule_binding_id)

    def rules(self):
        return self.get('/api/rules')

    def rule(self, rule_id):
        return self.get('/api/rules/%s' % rule_id)

    def upsert_rule(self, rule_config):
        path = '/api/rules/%s' % rule_config["id"]
        return self.put(path, rule_config)

    def delete_rule(self, rule_id):
        return self.delete('/api/rules/%s' % rule_id)

    def search_fields(self):
        return self.get('/api/searchFields')

    def service_extraction_configs(self):
        return self.get('/api/serviceExtractionConfigs')

    def upsert_service_extraction_configs(self, service_extraction_config):
        path = '/api/serviceExtractionConfigs/%s' % service_extraction_config["id"]
        return self.put(path, service_extraction_config)

    def snapshot(self, id, timestamp=None):
        params = {}
        if timestamp is not None:
            params['time'] = timestamp

        path = "/api/snapshots/%s" % id
        return self.get(path, query_args=params)

    def snapshots(self, query, timestamp=None, size=5):
        params = {'q': query, 'size': size}
        if timestamp is not None:
            params['time'] = timestamp

        path = "/api/snapshots"
        return self.get(path, query_args=params)

    def trace(self, trace_id):
        return self.get('/api/traces/%d' % trace_id)

    def traces_by_timeframe(self, query, window_size, ts_to, sort_by='ts', sort_mode='asc'):
        params = {'windowsize': window_size,
                  'to': ts_to,
                  'sortBy': sort_by,
                  'sortMode': sort_mode,
                  'query': query}
        return self.get('/api/traces', query_args=params)

    def roles(self):
        return self.get('/api/roles')

    def role(self, role_id):
        return self.get('/api/roles/%s' % role_id)

    def upsert_role(self, role_config):
        path = '/api/roles/%s' % role_config["id"]
        return self.put(path, payload=role_config)

    def delete_role(self, role_id):
        return self.delete('/api/roles/%s' % role_id)

    def users(self):
        return self.get('/api/tenant/users/overview')

    def set_user_role(self, user_id, role_id):
        return self.put('/api/tenant/users/%s/role' % user_id,
                        query_args={'roleId': role_id})

    def remove_user_from_tenant(self, user_id):
        return self.delete('/api/tenant/users/%s' % user_id)

    def invite_user(self, email, role_id):
        return self.post('/api/tenant/users/invitations',
                         query_args={'email', email, 'roleId', role_id})

    def revoke_pending_invitation(self, email):
        return self.delete('/api/tenant/users/invitations',
                           query_args={'email': email})

    def application_view(self):
        return self.get('/api/graph/views/application')

    def infrastructure_view(self):
        return self.get('/api/graph/views/infrastructure')

    def usage(self):
        return self.get('/api/usage/')

    def usage_for_month(self, year, month):
        return self.get('/api/usage/%d/%d' % (month, year))

    def usage_for_day(self, year, month, day):
        return self.get('/api/usage/%d/%d/%d' % (day, month, year))

    def average_number_of_hosts_for_month(self, year, month):
        return self.get('/api/usage/hosts/%d/%d' % (month, year))

    def average_number_of_hosts_for_day(self, year, month, day):
        return self.get('/api/usage/hosts/%d/%d/%d' % (month, year, day))
