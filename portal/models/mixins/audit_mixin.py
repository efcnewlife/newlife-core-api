"""
Audit information
"""
import pytz
import sqlalchemy as sa
from sqlalchemy import Column, DateTime, String, text, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr

from .context import get_current_id, get_current_username


class SortableMixin(object):
    """SortableMixin"""

    @declared_attr
    def sequence(self):
        """

        :return:
        """
        return Column(
            Float,
            server_default=text("extract(epoch from now())"),
            comment="Display sort, small to large, positive sort, default value current timestamp"
        )


class AuditCreatedAtMixin(object):
    """AuditCreatedAtMixin"""

    @declared_attr
    def created_at(self):
        """

        :return:
        """
        return Column(
            DateTime(timezone=True),
            server_default=sa.func.now(tz=pytz.UTC),
            comment="Create Date",
            nullable=False
        )


class AuditCreatedByMixin(object):
    """AuditCreatedByMixin"""

    @declared_attr
    def created_by(self):
        """

        :return:
        """
        return Column(
            String(64),
            default=get_current_username,
            comment="Create User Name",
            nullable=False
        )


class AuditCreatedMixin(AuditCreatedAtMixin, AuditCreatedByMixin):
    """AuditCreatedMixin"""

    @declared_attr
    def created_by_id(self):
        """

        :return:
        """
        return Column(UUID, default=get_current_id, comment="Create User ID")


class AuditUpdatedAtMixin(object):
    """AuditUpdatedAtMixin"""

    @declared_attr
    def updated_at(self):
        """

        :return:
        """
        return Column(
            DateTime(timezone=True),
            server_default=sa.func.now(tz=pytz.UTC),
            server_onupdate=sa.func.now(tz=pytz.UTC),
            onupdate=sa.func.now(tz=pytz.UTC),
            comment="Update Date",
            nullable=False
        )


class AuditUpdatedByMixin(object):
    """AuditUpdatedByMixin"""

    @declared_attr
    def updated_by(self):
        """

        :return:
        """
        return Column(
            String(64),
            default=get_current_username,
            comment="Update User Name",
            nullable=False
        )


class AuditUpdatedMixin(AuditUpdatedAtMixin, AuditUpdatedByMixin):
    """AuditUpdatedMixin"""

    @declared_attr
    def updated_by_id(self):
        return Column(
            UUID,
            default=get_current_id,
            onupdate=get_current_id,
            comment="Update User ID"
        )


class AuditMixin(AuditCreatedMixin, AuditUpdatedMixin):
    """AuditMixin"""
    pass


class DeletedMixin(object):
    """DeletedMixin"""

    @declared_attr
    def delete_reason(self):
        """

        :return:
        """
        return Column(String(64), comment="Delete Reason")

    @declared_attr
    def is_deleted(self):
        """

        :return:
        """
        return Column(
            Boolean,
            server_default=text("false"),
            comment="Is Deleted(Logical Delete)",
            nullable=False
        )


class DescriptionMixin(object):
    """DescriptionMixin"""

    @declared_attr
    def description(self):
        """

        :return:
        """
        return Column(sa.Text, comment="Description")


class RemarkMixin(object):
    """RemarkMixin"""

    @declared_attr
    def remark(self):
        """
        Remark
        :return:
        """
        return Column(String(256), comment="Remark")


class BaseMixin(AuditMixin, DeletedMixin, DescriptionMixin, RemarkMixin):
    """
    BaseMixin
    Contains audit information, logical deletion, description, and remark
    """
    pass
