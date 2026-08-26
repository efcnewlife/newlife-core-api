"""
Content Legal Document models (Product x Kind living Markdown).
"""

import sqlalchemy as sa
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, DeletedMixin
from portal.models.system_locale import SystemLocale


class ContentLegalDocument(ModelBase, AuditMixin, DeletedMixin):
    """Legal Document parent: one row per Product code x Kind."""

    __extra_table_args__ = (sa.UniqueConstraint("product", "kind"), sa.Index("ix_legal_document_product_kind_deleted", "product", "kind", "is_deleted"))

    product = Column(sa.String(64), nullable=False, comment="Built-in Product code")
    kind = Column(sa.String(64), nullable=False, comment="Legal Document Kind")

    translations = relationship("ContentLegalDocumentTranslation", back_populates="legal_document", passive_deletes=True)


class ContentLegalDocumentTranslation(ModelBase, AuditMixin):
    """Localized Markdown body for a Legal Document."""

    __extra_table_args__ = (sa.UniqueConstraint("legal_document_id", "locale_id"),)

    legal_document_id = Column(UUID, sa.ForeignKey(ContentLegalDocument.id, ondelete="CASCADE"), nullable=False, index=True, comment="Legal Document ID")
    locale_id = Column(UUID, sa.ForeignKey(SystemLocale.id, ondelete="CASCADE"), nullable=False, index=True, comment="Locale ID")
    body = Column(sa.Text, nullable=False, server_default=sa.text("''"), comment="Markdown body")

    legal_document = relationship("ContentLegalDocument", back_populates="translations", passive_deletes=True)
    locale = relationship("SystemLocale")
