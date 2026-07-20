"""
Content file models for uploaded file metadata and resource associations.
"""
import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from portal.domain.content.constants import FileStatus
from portal.libs.database.orm import ModelBase
from portal.models.mixins import AuditMixin, RemarkMixin, SortableMixin


class ContentFile(ModelBase, AuditMixin, RemarkMixin):
    """Uploaded file metadata."""

    __extra_table_args__ = (
        sa.UniqueConstraint("bucket", "key"),
    )

    original_name = Column(sa.String(255), nullable=False, comment="Original filename as uploaded")
    key = Column(sa.String(512), nullable=False, index=True, comment="Storage object key (path)")
    storage = Column(
        sa.String(16),
        nullable=False,
        default="azure_blob",
        comment="Storage backend, e.g., azure_blob, s3",
    )
    bucket = Column(sa.String(128), nullable=False, comment="Container or bucket name")
    region = Column(sa.String(32), nullable=False, comment="Storage region")
    content_type = Column(sa.String(128), nullable=True, comment="MIME type")
    extension = Column(sa.String(16), nullable=True, comment="File extension")
    size_bytes = Column(sa.BigInteger, nullable=True, comment="File size in bytes")
    checksum_md5 = Column(sa.String(32), nullable=True, comment="MD5 checksum")
    checksum_sha256 = Column(sa.String(64), nullable=True, comment="SHA-256 checksum")
    width = Column(sa.Integer, nullable=True, comment="Image width in pixels")
    height = Column(sa.Integer, nullable=True, comment="Image height in pixels")
    duration_seconds = Column(sa.Float, nullable=True, comment="Media duration in seconds")
    status = Column(
        sa.Integer,
        nullable=False,
        default=FileStatus.UPLOADING,
        comment="File status, refer to FileStatus enum",
    )
    version = Column(sa.Integer, nullable=False, default=1, comment="File version number")
    is_public = Column(
        sa.Boolean,
        server_default=sa.text("false"),
        nullable=False,
        comment="Whether the file is public",
    )
    source = Column(sa.Integer, nullable=True, comment="Upload source, refer to FileUploadSource")


class ContentFileAssociation(ModelBase, SortableMixin):
    """Link files to domain resources."""

    file_id = Column(
        UUID,
        ForeignKey(ContentFile.id, ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="File ID",
    )
    resource_id = Column(UUID, nullable=False, index=True, comment="Resource ID")
    resource_name = Column(
        sa.String(32),
        nullable=False,
        index=True,
        comment="Resource name (default table name)",
    )
