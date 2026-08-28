"""
Tests for graph mail override config.
"""

from portal.config import Configuration


def test_graph_mail_override_recipients_parses_comma_separated_addresses(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("GRAPH_MAIL_OVERRIDE_TO", " dev@local.test , qa@local.test ")
    config = Configuration()
    assert config.graph_mail_override_recipients() == ["dev@local.test", "qa@local.test"]


def test_graph_mail_override_recipients_ignored_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("GRAPH_MAIL_OVERRIDE_TO", "dev@local.test")
    config = Configuration()
    assert config.graph_mail_override_recipients() == []
