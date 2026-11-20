"""
Client IP: the one canonical visitor address shared by rate limiting, request/audit IP, and refresh-token last_ip.

TrustedIngressMiddleware resolves it once per request into the ASGI scope; consumers never read forwarding headers.
"""

import ipaddress
from typing import Optional

from starlette.requests import HTTPConnection
from starlette.types import Scope

CLIENT_IP_SCOPE_KEY = "newlife.client_ip"


def canonical_ip(value: str) -> Optional[str]:
    """
    One IPv4/IPv6 address in canonical text form; IPv4-mapped IPv6 becomes IPv4.
    :param value:
    :return: None for anything else (lists, zone IDs, hostnames, empty)
    """
    if "%" in value:
        return None
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return str(address.ipv4_mapped)
    return str(address)


def transport_peer_ip(scope: Scope) -> Optional[str]:
    """
    The canonical transport peer address, or None when the server reports none or a non-IP peer.
    :param scope:
    :return:
    """
    client = scope.get("client")
    return canonical_ip(client[0]) if client else None


def resolved_client_ip(connection: HTTPConnection) -> Optional[str]:
    """
    The client IP resolved by TrustedIngressMiddleware; without that middleware (bare test apps), the direct-mode peer.
    :param connection:
    :return:
    """
    scope = connection.scope
    if CLIENT_IP_SCOPE_KEY in scope:
        return scope[CLIENT_IP_SCOPE_KEY]
    return transport_peer_ip(scope)
