import re
from datetime import datetime, date

# integer
RE_INT = re.compile(r'^-?\d+$')
# numeral
RE_NUMBER = re.compile(r'^[-+]?\d+(\.\d+)?$')
# email
RE_EMAIL = re.compile(r'^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$', re.I)
# url
RE_URL = re.compile(r'^((https?|ftp|file)://).*', re.I)
# uuid
RE_UUID = re.compile(r'^[0-9a-f]{32}$', re.I)
# date yyyy-MM-dd
RE_DATE = re.compile(r'^\d{4}-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])$')
# date and time yyyy-MM-dd HH:mm:ss
RE_DATETIME = re.compile(r"""^\d{4}-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])\s+(0?[0-9]|1[0-9]|2[0-3]):([0-9]|[0-5][0-9]):([0-9]|[0-5][0-9])$""")

RE_DATETIME_MINUTE = re.compile(r"""^\d{4}-(0?[1-9]|1[0-2])-(0?[1-9]|[12][0-9]|3[01])\s+(0?[0-9]|1[0-9]|2[0-3]):([0-9]|[0-5][0-9])$""")


def is_null(value):
    return value is None


def is_empty(value):
    return value is None or value == ''


def is_email(value):
    if value is None:
        return False
    if not isinstance(value, str):
        return False
    if RE_EMAIL.findall(value):
        return True
    return False


def is_uuid(value: str):
    if value is None:
        return False
    import uuid
    if isinstance(value, uuid.UUID):
        return True
    if not isinstance(value, str):
        return False
    if RE_UUID.findall(value.replace('-', '')):
        return True
    return False


def is_bool(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    return value.lower() in ['true', 'false']


def is_number(value):
    if value is None:
        return False
    if isinstance(value, float) or isinstance(value, int):
        return True
    if not isinstance(value, str):
        return False
    if RE_NUMBER.findall(value):
        return True
    return False


def is_int(value):
    if value is None:
        return False
    if isinstance(value, int):
        return True
    if not isinstance(value, str):
        return False
    if RE_INT.findall(value):
        return True
    return False


def is_url(value):
    if value is None:
        return False
    if not isinstance(value, str):
        return False
    if RE_URL.findall(value):
        return True
    return False


def is_date(value):
    if value is None:
        return False
    if isinstance(value, date):
        return True
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    if RE_DATE.findall(value):
        return True
    return False


def is_datetime(value):
    if value is None:
        return False
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    if RE_DATETIME.findall(value):
        return True
    return False


def is_datetime_minute(value):
    if value is None:
        return False
    if isinstance(value, datetime):
        return True
    if not isinstance(value, str):
        return False
    if RE_DATETIME_MINUTE.findall(value):
        return True
    return False
