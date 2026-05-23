"""
Unit tests for MicrosoftOidcProvider.verify_id_token (mocked JWKS path).
"""
from unittest.mock import MagicMock, patch

import jwt
import pytest

from portal.config import settings
from portal.providers.microsoft_oidc_provider import MicrosoftOidcProvider


@pytest.fixture
def provider_configured(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setattr(settings, "AZURE_APP_CLIENT_ID", "22222222-2222-2222-2222-222222222222")
    yield


def test_is_configured_false_when_env_missing(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", None)
    monkeypatch.setattr(settings, "AZURE_APP_CLIENT_ID", None)
    provider = MicrosoftOidcProvider()
    assert provider.is_configured() is False
    with pytest.raises(jwt.InvalidTokenError):
        provider.verify_id_token("x.y.z")


@patch.object(MicrosoftOidcProvider, "is_configured", return_value=True)
def test_verify_id_token_propagates_pyjwt(mock_is_configured, provider_configured):
    provider = MicrosoftOidcProvider()
    mock_key = MagicMock()
    mock_key.key = "secret"
    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.return_value = mock_key
    provider._jwks_client = mock_jwks
    provider._spa_client_id = "22222222-2222-2222-2222-222222222222"
    provider._tenant_id = "11111111-1111-1111-1111-111111111111"

    with patch("portal.providers.microsoft_oidc_provider.jwt.decode", side_effect=jwt.InvalidTokenError("bad")):
        with pytest.raises(jwt.InvalidTokenError):
            provider.verify_id_token("header.payload.sig")
