"""
Tests for ministry application mail delivery overrides.
"""

from portal.application.org.ministry_application_mail_delivery import resolve_mail_delivery_targets


def test_resolve_mail_delivery_targets_uses_intended_recipient_by_default():
    recipients, prefix = resolve_mail_delivery_targets(intended_recipient="applicant@example.com", override_recipients=[])
    assert recipients == ["applicant@example.com"]
    assert prefix == ""


def test_resolve_mail_delivery_targets_redirects_to_override_recipients():
    recipients, prefix = resolve_mail_delivery_targets(intended_recipient="incumbent@example.com", override_recipients=["dev@local.test", "qa@local.test"])
    assert recipients == ["dev@local.test", "qa@local.test"]
    assert prefix == "[DEV -> incumbent@example.com] "


def test_resolve_mail_delivery_targets_skips_blank_intended_recipient():
    recipients, prefix = resolve_mail_delivery_targets(intended_recipient="  ", override_recipients=["dev@local.test"])
    assert recipients == []
    assert prefix == ""
