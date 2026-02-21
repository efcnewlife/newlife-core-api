import inspect
from portal.exceptions.responses import ParamError
from portal.libs.shared import validator


class Assert:
    @staticmethod
    def is_not_null(value, message: str):
        if value is None:
            raise ParamError(message)

    @staticmethod
    def is_not_empty(value, message: str):
        if validator.is_empty(value):
            raise ParamError(message)

    @staticmethod
    def is_not_number(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_number(value):
            raise ParamError(message)

    @staticmethod
    def is_not_int(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_int(value):
            raise ParamError(message)

    @staticmethod
    def is_not_email(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_email(value):
            raise ParamError(message)

    @staticmethod
    def is_not_function(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not inspect.isfunction(value):
            raise ParamError(message)

    @staticmethod
    def is_not_class(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not inspect.isclass(value):
            raise ParamError(message)

    @staticmethod
    def is_not_list(value, message: str = None, nullable=False):
        if nullable and value is None:
            return
        if not isinstance(value, list):
            raise ParamError(message)

    @staticmethod
    def is_not_dict(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not isinstance(value, dict):
            raise ParamError(message)

    @staticmethod
    def is_not_in_list(value, items: list, message: str, nullable=False):
        if nullable and value is None:
            return
        if value not in items:
            raise ParamError(message)

    @staticmethod
    def is_not_uuid(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_uuid(value):
            raise ParamError(message)

    @staticmethod
    def is_not_bool(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_bool(value):
            raise ParamError(message)

    @staticmethod
    def is_not_date(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_date(value):
            raise ParamError(message)

    @staticmethod
    def is_not_datetime(value, message: str, nullable=False):
        if nullable and value is None:
            return
        if not validator.is_datetime(value):
            raise ParamError(message)

    @staticmethod
    def is_not_dict_vals(item: dict, key: str, message: str):
        if not isinstance(item, dict):
            raise ParamError(message)
        value = item.get(key, None)
        if value is None or value == '':
            raise ParamError(message)
        return value
