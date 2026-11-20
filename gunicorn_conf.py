"""
Gunicorn settings for the container image.

Native ASGI worker; the app lifespan must run because it starts the Redis rate limiters and
the Pending-payment expiry sweep. Workers default to WEB_CONCURRENCY (gunicorn reads it), else 1.
FORWARDED_ALLOW_IPS (gunicorn reads it) affects only the scheme; scope client is always the socket peer.
Client IP resolution belongs to TrustedIngressMiddleware (docs/trusted-ingress.md).
"""

bind = "0.0.0.0:8000"
worker_class = "asgi"
asgi_lifespan = "on"
accesslog = "-"
errorlog = "-"
graceful_timeout = 30
