"""
Base serializers
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from dateutil import parser


class HeaderInfo(BaseModel):
    """
    Header information
    """
    accept_language: Optional[str] = Field(default="en-US", alias="accept-language", description="Accept-Language")
    # date: Optional[datetime] = Field(default=datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"), description="Date")
    # user_agent: Optional[str] = Field(..., description="User-Agent")
    # authorization: Optional[str] = Field(..., description="Authorization")
    # content_type: Optional[str] = Field(..., description="Content-Type")
    # content_length: Optional[str] = Field(..., description="Content-Length")
    # host: Optional[str] = Field(..., description="Host")
    # connection: Optional[str] = Field(..., description="Connection")
    # accept: Optional[str] = Field(..., description="Accept")
    # cache_control: Optional[str] = Field(..., description="Cache-Control")
    # accept_encoding: Optional[str] = Field(..., description="Accept-Encoding")
    # cookie: Optional[str] = Field(..., description="Cookie")
    # pragma: Optional[str] = Field(..., description="Pragma")
    # upgrade_insecure_requests: Optional[str] = Field(..., description="Upgrade-Insecure-Requests")
    # sec_fetch_user: Optional[str] = Field(..., description="Sec-Fetch-User")
    # sec_fetch_site: Optional[str] = Field(..., description="Sec-Fetch-Site")
    # sec_fetch_mode: Optional[str] = Field(..., description="Sec-Fetch-Mode")
    # sec_fetch_dest: Optional[str] = Field(..., description="Sec-Fetch-Dest")
    # referer: Optional[str] = Field(..., description="Referer")
    # accept_charset: Optional[str] = Field(..., description="Accept-Charset")
    # origin: Optional[str] = Field(..., description="Origin")

    # @field_validator("date", mode="before")
    # def date_serializer(cls, value: str) -> Optional[datetime]:
    #     """
    #
    #     :param value:
    #     :return:
    #     """
    #     try:
    #         return parser.parse(value)
    #     except Exception:
    #         return None
