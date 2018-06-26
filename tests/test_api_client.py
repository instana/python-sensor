import unittest

from nose.tools import assert_equals

from instana.api import APIClient

raise unittest.SkipTest("Manual tests due to API key requirement")

class TestAPIClient(object):
    def setUp(self):
        """ Clear all spans before a test run """
        self.client = APIClient()

    def tearDown(self):
        """ Do nothing for now """
        # after each test, tracer context should be None (not tracing)
        # assert_equals(None, tracer.current_context())
        return None

    def test_tokens(self):
        r = self.client.tokens()
        assert_equals(200, r.status)

    def test_token(self):
        r = self.client.token(self.client.api_token)
        assert_equals(200, r.status)

    @unittest.skip("")
    def test_delete_token(self):
        None

    @unittest.skip("")
    def upsert_token(self):
        None

    def test_audit_log(self):
        r = self.client.audit_log()
        assert_equals(200, r.status)

    def test_eum_apps(self):
        r = self.client.eum_apps()
        assert_equals(200, r.status)

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
        r = self.client.events()
        assert_equals(200, r.status)

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
        r = self.client.rule_bindings()
        assert_equals(200, r.status)

    @unittest.skip("")
    def test_rule_binding(self):
        None

    def test_rules(self):
        r = self.client.rules()
        assert_equals(200, r.status)

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
        r = self.client.search_fields()
        assert_equals(200, r.status)

    def test_service_extraction_configs(self):
        r = self.client.rules()
        assert_equals(200, r.status)

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
        r = self.client.roles()
        assert_equals(200, r.status)

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
        r = self.client.users()
        assert_equals(200, r.status)

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
        r = self.client.application_view()
        assert_equals(200, r.status)

    def test_infrastructure_view(self):
        r = self.client.infrastructure_view()
        assert_equals(200, r.status)

    def test_usage(self):
        r = self.client.usage()
        assert_equals(200, r.status)

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
