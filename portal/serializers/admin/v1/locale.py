"""
Admin Locale Serializer
"""
from pydantic import Field, BaseModel

from portal.schemas.locale import SLocale


class AdminLocaleList(BaseModel):
    """LocaleList"""
    items: list[SLocale] = Field(..., description="Items")
