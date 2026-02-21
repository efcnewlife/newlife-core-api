"""
Converter class for converting various data types.
"""
import re
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import TypeVar, Union, Any

from portal.exceptions.validation_errors import (
    IntError,
    FloatError,
    BoolError,
    DateError,
    DateTimeError,
    UUIDError,
    ListError,
)
from portal.libs.shared import validator

T = TypeVar('T')


class Converter:

    @classmethod
    def to_int(cls, value: Union[str, int, float], default: int = None, raise_error: bool = False):
        """
        :param value:
        :param default:
        :param raise_error:
        :return:
        """
        if isinstance(value, int):
            return value
        if validator.is_int(value):
            return int(value)
        if raise_error:
            raise IntError(value)
        return default or value

    @classmethod
    def to_bool(cls, value: Union[str, bool], default: bool = None, raise_error: bool = False):
        """
        :param raise_error:
        :param value:
        :param default:
        :return:
        """
        if isinstance(value, bool):
            return value
        if validator.is_bool(value):
            return value.lower() == 'true'
        if raise_error:
            raise BoolError(value)
        if default is not None:
            return default or value
        return False

    @classmethod
    def to_float(cls, value, default: float = None, raise_error: bool = False):
        if validator.is_number(value):
            return float(value)
        if raise_error:
            raise FloatError(value)
        return default or value

    @classmethod
    def to_datetime(cls, value, default=None, raise_error: bool = False):
        """
        :param raise_error:
        :param value:
        :param default:
        :return:
        """
        if isinstance(value, datetime):
            return value
        if validator.is_datetime(value):
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if validator.is_datetime_minute(value):
            return datetime.strptime(value, '%Y-%m-%d %H:%M')
        if validator.is_date(value):
            return datetime.strptime(value, '%Y-%m-%d')
        if raise_error:
            raise DateTimeError(value)
        return default or value

    @classmethod
    def to_date(cls, value: Any, default: date = None, raise_error: bool = False):
        """
        :param raise_error:
        :param value:
        :param default:
        :return:
        """
        if isinstance(value, date):
            return value
        if validator.is_date(value):
            dt = datetime.strptime(value, '%Y-%m-%d')
            return date(dt.year, dt.month, dt.day)
        if raise_error:
            raise DateError(value)
        return default or value

    @classmethod
    def to_hms(cls, value, default: tuple = (0, 0, 0), raise_error: bool = False):
        """
        :param value:
        :param default:
        :param raise_error:
        :return:
        """
        if isinstance(value, int) or isinstance(value, float):
            m, s = divmod(value, 60)
            h, m = divmod(m, 60)
            return int(h), int(m), format(s, ".1f")
        if raise_error:
            raise TypeError(f'{value} is not a valid int or float type')
        return default

    @classmethod
    def to_uuid(cls, value, default=None, raise_error: bool = False):
        if isinstance(value, uuid.UUID):
            return value
        if validator.is_uuid(value):
            return uuid.UUID(value)
        if raise_error:
            raise UUIDError(value)
        return default

    @classmethod
    def to_uuid_hex(cls, value):
        result = cls.to_uuid(value)
        if not result:
            return result
        return result.hex

    @classmethod
    def to_list(cls, value: Union[str, list], separator: str = ',', default_value: list = None):
        if not value:
            return default_value
        if isinstance(value, list):
            return value
        if isinstance(value, set):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, str):
            return re.split(separator, value)
        raise ListError(value)

    @classmethod
    def format_value(cls, value: Any):
        if isinstance(value, uuid.UUID):
            return value
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        elif isinstance(value, Decimal):
            return int(value)
        return value


__all__ = [
    "Converter",
]
