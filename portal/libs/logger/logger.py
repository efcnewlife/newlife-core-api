"""
Logger
"""
import logging

from portal.config import settings
from .generator import LoggerGenerator


__all__ = [
    "logger"
]


def get_logger(app_name: str, env: str) -> logging.Logger:
    """

    :param app_name:
    :param env:
    :return:
    """
    return (
        LoggerGenerator(app_name)
        .set_level_by_env(env)
        .add_handler(logging.StreamHandler())
        .get()
    )


__logger = get_logger(settings.APP_NAME, settings.ENV.upper())
logger = __logger
