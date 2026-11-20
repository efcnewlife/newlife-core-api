"""
Entry point for running portal app
"""

import uvicorn

from portal.config import settings

if __name__ == "__main__":
    # Forwarding headers never rewrite the peer; TrustedIngressMiddleware owns client IP resolution.
    uvicorn.run("portal.main:app", host=settings.HOST, port=settings.PORT, reload=settings.is_dev, proxy_headers=False)
