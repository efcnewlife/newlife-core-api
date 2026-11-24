"""
Configuration loads in a clean container environment (no .env file, only required variables set).
"""

from uuid import uuid4

from portal.config import Configuration


def test_unset_list_setting_keeps_its_default(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    config = Configuration()

    assert config.CORS_ALLOWED_ORIGINS == Configuration.model_fields["CORS_ALLOWED_ORIGINS"].default


def test_list_setting_splits_on_commas(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://portal.efcnewlife.com,https://portal.dev.efcnewlife.com")

    config = Configuration()

    assert config.CORS_ALLOWED_ORIGINS == ["https://portal.efcnewlife.com", "https://portal.dev.efcnewlife.com"]


def test_trusted_proxy_mode_defaults_to_direct(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_MODE", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ORIGIN_SECRET", raising=False)

    config = Configuration()

    assert config.TRUSTED_PROXY_MODE == "direct"
    assert config.CLOUDFLARE_ORIGIN_SECRET is None


def test_cloudflare_origin_secret_is_hidden_from_the_configuration_repr(monkeypatch):
    secret = f"origin-{uuid4().hex}"
    monkeypatch.setenv("CLOUDFLARE_ORIGIN_SECRET", secret)

    config = Configuration()

    assert config.CLOUDFLARE_ORIGIN_SECRET.get_secret_value() == secret
    assert secret not in repr(config) and secret not in str(config)


def test_database_pool_max_size_defaults_to_30(monkeypatch):
    monkeypatch.delenv("DATABASE_POOL_MAX_SIZE", raising=False)

    assert Configuration().DATABASE_POOL_MAX_SIZE == 30


def test_database_pool_max_size_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_POOL_MAX_SIZE", "80")

    assert Configuration().DATABASE_POOL_MAX_SIZE == 80
