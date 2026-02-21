"""
Logger generator
"""
import logging
import sys

from .const import (
    DEFAULT_LOG_LEVEL,
    MAP_ENV_LEVEL,
    DEFAULT_FORMAT,
    DEFAULT_FORMAT_DATE,
)


class LoggerGenerator:
    """Logger generator"""
    def __init__(self, logger_name: str):
        self.logger_name = logger_name
        self.formatter = logging.Formatter(
            DEFAULT_FORMAT,
            datefmt=DEFAULT_FORMAT_DATE
        )
        self.log_level = DEFAULT_LOG_LEVEL
        self.handlers = []

    class __LogLevelFilter(logging.Filter):
        def __init__(self, levels: tuple):
            super().__init__()
            self.target_levels = levels

        def filter(self, rec):
            return rec.levelno in self.target_levels

    def set_level_by_env(self, env: str):
        """

        :param env:
        :return:
        """
        env = env.lower()
        if env in MAP_ENV_LEVEL.keys():
            self.log_level = MAP_ENV_LEVEL[env]
        else:
            self.log_level = logging.INFO
        return self

    def add_handler(self, handler: logging.StreamHandler):
        """

        :param handler:
        :return:
        """
        handler.setLevel(self.log_level)
        handler.setFormatter(self.formatter)
        handler.addFilter(self.__LogLevelFilter((logging.WARNING, logging.ERROR, logging.CRITICAL)))
        self.handlers.append(handler)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(handler.level)
        stdout_handler.setFormatter(handler.formatter)
        stdout_handler.addFilter(self.__LogLevelFilter((logging.DEBUG, logging.INFO)))
        self.handlers.append(stdout_handler)
        return self

    def get(self):
        if not self.handlers:
            raise ValueError("No handler is set for the logger, please use add_handler")
        logger = logging.getLogger(self.logger_name)

        logger.handlers.clear()  # To sure there is no duplicate logger in the same logger_name
        logger.addHandler(logging.NullHandler())

        logger = logging.getLogger(self.logger_name)
        logger.setLevel(self.log_level)

        for handler in self.handlers:
            logger.addHandler(handler)

        return logger
