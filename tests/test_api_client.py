from nose.tools import assert_equals
from instana.api import APIClient
import unittest

client = APIClient()


@unittest.skip("Manual tests due to API key requirement")
class TestAPIClient(object):
    def test_tokens(self):
        r = client.tokens()
        assert_equals(200, r.status_code)

    def test_token(self):
        r = client.token(client.api_token)
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_delete_token(self):
        None

    @unittest.skip("")
    def upsert_token(self):
        None

    def test_audit_log(self):
        r = client.audit_log()
        assert_equals(200, r.status_code)

    def test_eum_apps(self):
        r = client.eum_apps()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_create_eum_app(self):
        None

    @unittest.skip("")
    def test_rename_eum_app(self):
        None

    @unittest.skip("")
    def test_delete_eum_app(self):
        None

    def test_events(self):
        r = client.events()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_event(self):
        None

    @unittest.skip("")
    def test_metrics(self):
        None

    @unittest.skip("")
    def test_metric(self):
        None

    def test_rule_bindings(self):
        r = client.rule_bindings()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_rule_binding(self):
        None

    def test_rules(self):
        r = client.rules()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_rule(self):
        None

    @unittest.skip("")
    def test_upsert_rule(self):
        None

    @unittest.skip("")
    def test_delete_rule(self):
        None

    def test_search_fields(self):
        r = client.search_fields()
        assert_equals(200, r.status_code)

    def test_service_extraction_configs(self):
        r = client.rules()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_upsert_service_extraction_configs(self):
        None

    @unittest.skip("")
    def test_snapshot(self):
        None

    @unittest.skip("")
    def test_snapshots(self):
        None

    @unittest.skip("")
    def test_trace(self):
        None

    @unittest.skip("")
    def test_traces_by_timeframe(self):
        None

    def test_roles(self):
        r = client.roles()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_role(self):
        None

    @unittest.skip("")
    def test_upsert_role(self):
        None

    @unittest.skip("")
    def test_delete_role(self):
        None

    def test_users(self):
        r = client.users()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_set_user_role(self):
        None

    @unittest.skip("")
    def test_remove_user_from_tenant(self):
        None

    @unittest.skip("")
    def test_invite_user(self):
        None

    @unittest.skip("")
    def test_revoke_pending_invitation(self):
        None

    def test_application_view(self):
        r = client.application_view()
        assert_equals(200, r.status_code)

    def test_infrastructure_view(self):
        r = client.infrastructure_view()
        assert_equals(200, r.status_code)

    def test_usage(self):
        r = client.usage()
        assert_equals(200, r.status_code)

    @unittest.skip("")
    def test_usage_for_month(self):
        None

    @unittest.skip("")
    def test_usage_for_day(self):
        None

    @unittest.skip("")
    def test_average_number_of_hosts_for_month(self):
        None

    @unittest.skip("")
    def test_average_number_of_hosts_for_day(self):
        None
