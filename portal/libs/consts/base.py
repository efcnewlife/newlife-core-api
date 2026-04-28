"""
Base Constants
"""

BEARER_AUTH = {
    "BearerAuth": []
}

ROUTER_SECURITY = [
    BEARER_AUTH,
]

BEARER_AUTH_SCHEME = {
    "type": "http",
    "scheme": "bearer"
}

SECURITY_SCHEMES = {
    "BearerAuth": BEARER_AUTH_SCHEME,
}
