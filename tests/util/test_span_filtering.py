# (c) Copyright IBM Corp. 2025

from instana.util.config import get_span_filter_config_from_yaml


class TestSpanFilteringExamples:
    def test_load_span_filtering_examples(self, monkeypatch) -> None:
        monkeypatch.setenv(
            "INSTANA_CONFIG_PATH", "tests/util/test_span_filtering_configuration.yaml"
        )
        span_filters = get_span_filter_config_from_yaml()

        # Verify deactivate is false (default)
        assert span_filters["deactivate"] is False

        # Verify include rules count (9 examples)
        assert len(span_filters["include"]) == 9

        # Verify exclude rules count (33 examples)
        assert len(span_filters["exclude"]) == 33

        # Spot check some specific rules

        # Check first exclude rule: "HTTP for filtering context root"
        first_exclude = span_filters["exclude"][0]
        assert first_exclude["name"] == "HTTP for filtering context root"
        assert len(first_exclude["attributes"]) == 2
        assert first_exclude["attributes"][1] == {
            "key": "http.context_root",
            "values": ["/health"],
            "match_type": "strict",
        }

        # Check an include rule: "HTTP Include Endswith URL"
        first_include = span_filters["include"][0]
        assert first_include["name"] == "HTTP Include Endswith URL"
        assert len(first_include["attributes"]) == 3
        assert first_include["attributes"][2] == {
            "key": "http.url",
            "match_type": "endswith",
            "values": ["/dawg"],
        }

        # Check a specific JMS rule: "JMS Sort Entry"
        jms_rule = next(
            r for r in span_filters["exclude"] if r["name"] == "JMS Sort Entry"
        )
        assert jms_rule["attributes"][1] == {
            "key": "jms.sort",
            "values": ["entry"],
            "match_type": "contains",
        }

        # Check a specific Kafka rule: "Kafka Kind"
        kafka_rule = next(
            r for r in span_filters["exclude"] if r["name"] == "Kafka Kind"
        )
        assert kafka_rule["attributes"][1] == {
            "key": "kind",
            "values": ["entry", "exit"],
        }


# Made with Bob
