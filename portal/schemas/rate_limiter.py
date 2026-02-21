"""
Rate limiter configuration schemas
"""
from pydantic import BaseModel, Field


class RateLimitWindow(BaseModel):
    """
    Rate limit window configuration
    """
    times: int = Field(..., description="Number of requests allowed", gt=0)
    seconds: int = Field(..., description="Time window in seconds", gt=0)


class RateLimiterConfig(BaseModel):
    """
    Rate limiter configuration for a specific endpoint type
    """
    short: RateLimitWindow = Field(..., description="Short-term rate limit (e.g., 1 second)")
    medium: RateLimitWindow = Field(..., description="Medium-term rate limit (e.g., 30 seconds)")
    long: RateLimitWindow = Field(..., description="Long-term rate limit (e.g., 1 hour)")


class RateLimitersConfig(BaseModel):
    """
    Complete rate limiters configuration
    """
    default: RateLimiterConfig = Field(..., description="Default rate limiter configuration for general endpoints")
    read: RateLimiterConfig = Field(..., description="Rate limiter configuration for read endpoints (more lenient)")
    write: RateLimiterConfig = Field(..., description="Rate limiter configuration for write endpoints (more strict)")

