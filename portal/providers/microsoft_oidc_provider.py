"""
Verify Microsoft Entra ID (v2) ID tokens using JWKS.
"""
from typing import Any, Optional

import jwt
from jwt import PyJWKClient

from portal.config import settings
from portal.libs.logger import logger


class MicrosoftOidcProvider:
    """Validate Entra ID tokens issued to the Admin Portal SPA."""

    def __init__(self) -> None:
        self._tenant_id = settings.AZURE_TENANT_ID
        self._spa_client_id = settings.AZURE_APP_CLIENT_ID
        self._jwks_url: Optional[str] = None
        self._jwks_client: Optional[PyJWKClient] = None
        if self._tenant_id:
            self._jwks_url = (
                f"https://login.microsoftonline.com/{self._tenant_id}/discovery/v2.0/keys"
            )
            self._jwks_client = PyJWKClient(self._jwks_url, cache_keys=True)

    def is_configured(self) -> bool:
        return bool(self._tenant_id and self._spa_client_id and self._jwks_client)

    def _allowed_issuers(self) -> list[str]:
        if settings.AZURE_ALLOWED_ISSUERS:
            return [s.strip() for s in settings.AZURE_ALLOWED_ISSUERS.split(",") if s.strip()]
        return [f"https://login.microsoftonline.com/{self._tenant_id}/v2.0"]

    def verify_id_token(self, token: str) -> dict[str, Any]:
        """
        Decode and validate an ID token. Returns claims on success.
        :raises jwt.PyJWTError: if the token is invalid
        """
        if not self.is_configured():
            raise jwt.InvalidTokenError("Microsoft Entra ID is not configured")

        assert self._jwks_client is not None
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        issuers = self._allowed_issuers()
        last_error: Optional[Exception] = None
        for issuer in issuers:
            try:
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self._spa_client_id,
                    issuer=issuer,
                    options={"require": ["exp", "sub", "aud", "iss"]},
                    leeway=120,
                )
            except jwt.PyJWTError as exc:
                last_error = exc
                logger.debug("ID token issuer validation failed for %s: %s", issuer, exc)
                continue
        if last_error:
            raise last_error
        raise jwt.InvalidTokenError("No valid issuer")
