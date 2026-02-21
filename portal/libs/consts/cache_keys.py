"""
Constants for Cache keys
"""
from portal.config import settings


class CacheExpiry:
    """
    Cache expiry times in seconds
    """
    HOUR = 3600
    DAY = 86400
    WEEK = 604800
    MONTH = 2592000
    YEAR = 31536000


class CacheKeys:

    def __init__(self, resource: str):
        self._app_name = settings.APP_NAME
        self.resource = resource
        self.attributes = []

    def build(self) -> str:
        """
        Build cache key (no trailing separator).
        :return:
        """
        parts = "".join(self.attributes).rstrip(":")
        return f"{self._app_name}:{self.resource}:{parts}" if parts else f"{self._app_name}:{self.resource}"

    def add_attribute(self, attribute: str, separator: str = ":") -> "CacheKeys":
        """
        add_attribute
        :param attribute:
        :param separator:
        :return:
        """
        self.attributes.extend([attribute, separator])
        return self
