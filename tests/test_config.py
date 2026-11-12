"""
Configuration loads in a clean container environment (no .env file, only required variables set).
"""

from portal.config import Configuration


def test_unset_list_setting_keeps_its_default(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    config = Configuration()

    assert config.CORS_ALLOWED_ORIGINS == Configuration.model_fields["CORS_ALLOWED_ORIGINS"].default


def test_list_setting_splits_on_commas(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://portal.efcnewlife.com,https://portal.dev.efcnewlife.com")

    config = Configuration()

    assert config.CORS_ALLOWED_ORIGINS == ["https://portal.efcnewlife.com", "https://portal.dev.efcnewlife.com"]
