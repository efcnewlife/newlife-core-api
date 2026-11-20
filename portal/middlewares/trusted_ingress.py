"""
Trusted ingress: authenticate the edge and resolve the client IP before CORS, mounted apps, or rate limiters run.

direct (default): forwarding headers are ignored; the transport peer is the client.
cloudflare: every request except GET/HEAD /healthz needs exactly one matching X-NewLife-Origin-Secret, the
APP_FQDN host, and exactly one valid CF-Connecting-IP. The secret header never reaches the application.
"""

import hmac
from typing import Optional

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from portal.config import Configuration
from portal.libs.client_ip import CLIENT_IP_SCOPE_KEY, canonical_ip, transport_peer_ip
from portal.libs.logger import logger

DIRECT_MODE = "direct"
CLOUDFLARE_MODE = "cloudflare"
ORIGIN_SECRET_HEADER = b"x-newlife-origin-secret"
CLIENT_IP_HEADER = b"cf-connecting-ip"
MIN_ORIGIN_SECRET_LENGTH = 32
# App Service passes an unresolved Key Vault reference through as its own text, which is public in newlife-infra.
_KEY_VAULT_REFERENCE_PREFIX = "@microsoft.keyvault("
# App Service health check probes the origin without the zone secret; it gets no trusted client IP.
_LIVENESS_PATH = "/healthz"
_LIVENESS_METHODS = frozenset({"GET", "HEAD"})
# Policy violation: the connection did not come through the trusted edge.
_WEBSOCKET_POLICY_VIOLATION = 1008


class TrustedProxyConfigError(RuntimeError):
    """Invalid trusted proxy settings. The message names the setting, never its value."""


class IngressPolicy:
    def __init__(self, mode: str, origin_secret: bytes = b"", expected_host: str = ""):
        self.mode = mode
        self._origin_secret = origin_secret
        self._expected_host = expected_host

    @classmethod
    def from_settings(cls, config: Configuration) -> "IngressPolicy":
        """
        :param config:
        :return:
        :raises TrustedProxyConfigError: cloudflare mode without a usable secret (missing, short, or an unresolved Key Vault reference) or host, or an unknown mode
        """
        mode = (config.TRUSTED_PROXY_MODE or "").strip().lower()
        if mode == DIRECT_MODE:
            return cls(mode)
        if mode != CLOUDFLARE_MODE:
            raise TrustedProxyConfigError(f"TRUSTED_PROXY_MODE must be '{DIRECT_MODE}' or '{CLOUDFLARE_MODE}'")
        # Stripped once for both checks: a stray newline in the Key Vault value must not reject every request.
        secret = config.CLOUDFLARE_ORIGIN_SECRET.get_secret_value().strip() if config.CLOUDFLARE_ORIGIN_SECRET else ""
        if len(secret) < MIN_ORIGIN_SECRET_LENGTH:
            raise TrustedProxyConfigError(f"CLOUDFLARE_ORIGIN_SECRET must be at least {MIN_ORIGIN_SECRET_LENGTH} characters in cloudflare mode")
        if secret.lower().startswith(_KEY_VAULT_REFERENCE_PREFIX):
            raise TrustedProxyConfigError("CLOUDFLARE_ORIGIN_SECRET is an unresolved Key Vault reference")
        expected_host = (config.APP_FQDN or "").strip().lower()
        if not expected_host:
            raise TrustedProxyConfigError("APP_FQDN is required in cloudflare mode")
        return cls(mode, secret.encode("utf-8"), expected_host)

    def verify(self, headers: list[tuple[bytes, bytes]]) -> tuple[Optional[str], Optional[str]]:
        """
        Cloudflare mode only.
        :param headers: Raw ASGI headers
        :return: (client IP, None) when trusted, else (None, a fixed rejection log message without any header value)
        """
        secrets = [value for name, value in headers if name == ORIGIN_SECRET_HEADER]
        if len(secrets) != 1 or not hmac.compare_digest(secrets[0], self._origin_secret):
            return None, "Rejected request from untrusted ingress: invalid origin secret"
        hosts = [value for name, value in headers if name == b"host"]
        if len(hosts) != 1 or hosts[0].decode("latin-1").lower() != self._expected_host:
            return None, "Rejected request from untrusted ingress: invalid host"
        client_ips = [value for name, value in headers if name == CLIENT_IP_HEADER]
        client_ip = canonical_ip(client_ips[0].decode("latin-1")) if len(client_ips) == 1 else None
        if client_ip is None:
            return None, "Rejected request from untrusted ingress: invalid client IP"
        return client_ip, None


def _is_liveness_probe(scope: Scope) -> bool:
    return scope["type"] == "http" and scope["method"] in _LIVENESS_METHODS and scope["path"] == _LIVENESS_PATH


class TrustedIngressMiddleware:
    """Outermost middleware of the public application, so it also covers CORS preflight and mounted apps."""

    def __init__(self, app: ASGIApp, policy: IngressPolicy):
        self.app = app
        self.policy = policy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = scope["headers"]
        scope["headers"] = [(name, value) for name, value in headers if name != ORIGIN_SECRET_HEADER]
        if self.policy.mode == DIRECT_MODE:
            scope[CLIENT_IP_SCOPE_KEY] = transport_peer_ip(scope)
        elif _is_liveness_probe(scope):
            scope[CLIENT_IP_SCOPE_KEY] = None
        else:
            client_ip, rejection = self.policy.verify(headers)
            if client_ip is None:
                # The whole message is the template: Sentry keeps templates and drops string parameters (ADR 0038).
                logger.warning(rejection)
                await self._reject(scope, receive, send)
                return
            scope[CLIENT_IP_SCOPE_KEY] = client_ip
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": _WEBSOCKET_POLICY_VIOLATION})
            return
        await JSONResponse(content={"detail": "Forbidden"}, status_code=403)(scope, receive, send)
