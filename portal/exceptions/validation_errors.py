from typing import Any


class ValidationError(Exception):
    pass


class ConvertError(ValidationError):
    def __init__(self, value: Any, except_type: Any):
        super().__init__(f'Attempt to convert "{value}" to {except_type} type failed')


class IntError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to int type failed')


class FloatError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to float type failed')


class BoolError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to bool type failed')


class DateError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to date type failed')


class DateTimeError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to datetime type failed')


class UUIDError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to uuid type failed')


class ListError(ValidationError):
    def __init__(self, value: Any):
        super().__init__(f'Attempt to convert "{value}" to list type failed')
