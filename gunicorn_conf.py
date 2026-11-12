"""
Gunicorn settings for the container image.

Native ASGI worker; the app lifespan must run because it starts the Redis rate limiters and
the Pending-payment expiry sweep. Workers default to WEB_CONCURRENCY (gunicorn reads it), else 1.
Trusted proxy addresses come from FORWARDED_ALLOW_IPS (gunicorn reads it).
"""

bind = "0.0.0.0:8000"
worker_class = "asgi"
asgi_lifespan = "on"
accesslog = "-"
errorlog = "-"
graceful_timeout = 30
