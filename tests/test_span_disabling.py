# (c) Copyright IBM Corp. 2025

import pytest

from instana.options import BaseOptions, StandardOptions
from instana.singletons import agent


class TestSpanDisabling:
    @pytest.fixture(autouse=True)
    def setup(self):
        # Save original options
        self.original_options = agent.options
        yield
        # Restore original options
        agent.options = self.original_options

    def test_is_span_disabled_default(self):
        options = BaseOptions()
        assert not options.is_span_disabled(category="logging")
        assert not options.is_span_disabled(category="databases")
        assert not options.is_span_disabled(span_type="redis")

    def test_disable_category(self):
        options = BaseOptions()
        options.disabled_spans = ["logging"]
        assert options.is_span_disabled(category="logging")
        assert not options.is_span_disabled(category="databases")

    def test_disable_type(self):
        options = BaseOptions()
        options.disabled_spans = ["redis"]
        assert options.is_span_disabled(span_type="redis")
        assert not options.is_span_disabled(span_type="mysql")

    def test_type_category_relationship(self):
        options = BaseOptions()
        options.disabled_spans = ["databases"]
        assert options.is_span_disabled(span_type="redis")
        assert options.is_span_disabled(span_type="mysql")

    def test_precedence_rules(self):
        options = BaseOptions()
        options.disabled_spans = ["databases"]
        options.enabled_spans = ["redis"]
        assert options.is_span_disabled(category="databases")
        assert options.is_span_disabled(span_type="mysql")
        assert not options.is_span_disabled(span_type="redis")

    @pytest.mark.parametrize("value", ["True", "true", "1"])
    def test_env_var_disable_all(self, value, monkeypatch):
        monkeypatch.setenv("INSTANA_TRACING_DISABLE", value)
        options = BaseOptions()
        assert options.is_span_disabled(category="logging") is True
        assert options.is_span_disabled(category="databases") is True
        assert options.is_span_disabled(category="messaging") is True
        assert options.is_span_disabled(category="protocols") is True

    def test_env_var_disable_specific(self, monkeypatch):
        monkeypatch.setenv("INSTANA_TRACING_DISABLE", "logging, redis")
        options = BaseOptions()
        assert options.is_span_disabled(category="logging") is True
        assert options.is_span_disabled(category="databases") is False
        assert options.is_span_disabled(span_type="redis") is True
        assert options.is_span_disabled(span_type="mysql") is False

    def test_yaml_config(self):
        options = StandardOptions()
        tracing_config = {
            "disable": [{"logging": True}, {"redis": False}, {"databases": True}]
        }
        options.set_tracing(tracing_config)
        assert options.is_span_disabled(category="logging")
        assert options.is_span_disabled(category="databases")
        assert options.is_span_disabled(span_type="mysql")
        assert not options.is_span_disabled(span_type="redis")


# Made with Bob
