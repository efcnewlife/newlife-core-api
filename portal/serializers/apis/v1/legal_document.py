"""
Member public Legal Document serializers.
"""

from datetime import date

from pydantic import BaseModel, Field


class MemberLegalDocumentPublic(BaseModel):
    """Unauthenticated Legal Document read response."""

    product: str = Field(..., description="Built-in Product code")
    kind: str = Field(..., description="Legal Document Kind")
    body: str = Field(default="", description="Markdown body for resolved locale")
    effective_date: date = Field(..., serialization_alias="effectiveDate", description="Effective Date (calendar day)")
