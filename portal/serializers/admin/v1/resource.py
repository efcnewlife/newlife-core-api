"""
Resource serializers
"""
from typing import Optional
from uuid import UUID

from pydantic import Field, BaseModel, field_validator, model_validator

from portal.libs.consts.enums import ResourceType
from portal.serializers.mixins.model_mixins import UUIDBaseModel, JSONStringMixinModel
from portal.serializers.admin.v1.translation import (
    AdminTranslationInput,
    validate_unique_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.base import ChangeSequence


class AdminResourceBase(UUIDBaseModel):
    """ResourceBase"""
    name: str = Field(..., description="Name")
    key: str = Field(..., description="Key")
    code: str = Field(..., description="Code")
    icon: Optional[str] = Field(None, description="Icon")


class AdminResourceItem(AdminResourceBase):
    """ResourceItem"""
    pid: Optional[UUID] = Field(None, description="Parent resource id")
    path: Optional[str] = Field(None, description="Path")
    type: ResourceType = Field(..., description="Resource type")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")
    sequence: float = Field(..., description="Sequence")
    is_deleted: bool = Field(False, description="Is deleted")


class AdminResourceParent(AdminResourceBase, JSONStringMixinModel):
    """ResourceParent"""
    id: Optional[UUID] = Field(None, description="Resource id")
    name: Optional[str] = Field(None, description="Name")
    key: Optional[str] = Field(None, description="Key")
    code: Optional[str] = Field(None, description="Code")
    icon: Optional[str] = Field(None, description="Icon")


class AdminResourceDetail(AdminResourceItem):
    """ResourceDetail"""
    pid: Optional[UUID] = Field(None, description="Parent resource id", exclude=True)
    parent: Optional[AdminResourceParent] = Field(None, description="Parent resource")


class AdminResourcePages(PaginationBaseResponseModel):
    """ResourcePages"""
    items: Optional[list[AdminResourceItem]] = Field(..., description="Resource Items")


class AdminResourceList(BaseModel):
    """ResourceList"""
    items: Optional[list[AdminResourceItem]] = Field(..., description="Resource Items")


class AdminResourceTreeItem(AdminResourceItem):
    """Resource Tree Item"""
    children: Optional[list["AdminResourceTreeItem"]] = Field(None, description="Resource children")

    @field_validator('children')
    def validate_children_depth(cls, v):
        """validate children depth not exceed limit"""
        if v is not None:
            for child in v:
                cls.validate_node_depth(child, 1)  # start from second level
        return v

    @classmethod
    def validate_node_depth(cls, node: "AdminResourceTreeItem", current_depth: int):
        """validate node depth"""
        if current_depth > 2:
            raise ValueError("Tree structure exceeds three levels limit")

        if node.children:
            for child in node.children:
                cls.validate_node_depth(child, current_depth + 1)


class AdminResourceTree(BaseModel):
    """Resource Tree - Max 2 levels"""
    items: Optional[list[AdminResourceTreeItem]] = Field(None, description="Root resource items")

    @field_validator('items')
    def validate_tree_depth(cls, v):
        """validate tree depth not exceed limit"""
        if v:
            for root in v:
                AdminResourceTreeItem.validate_node_depth(root, 1)  # start from first level
        return v


class AdminResourceWrite(BaseModel):
    """ResourceWrite"""
    pid: Optional[UUID] = Field(None, description="Parent resource id")
    name: Optional[str] = Field(None, description="Name")
    key: str = Field(..., description="Key")
    code: str = Field(..., description="Code")
    icon: str = Field(..., description="Icon")
    path: str = Field(..., description="Path")
    type: ResourceType = Field(..., description="Resource type")
    is_visible: bool = Field(True, description="Is visible")
    description: Optional[str] = Field(None, description="Description")
    remark: Optional[str] = Field(None, description="Remark")
    translations: Optional[list[AdminTranslationInput]] = Field(None, description="Localized content")

    @field_validator("translations")
    @classmethod
    def validate_translations_locale_ids(cls, value: Optional[list[AdminTranslationInput]]) -> Optional[list[AdminTranslationInput]]:
        return validate_unique_locale_ids(value)


class AdminResourceCreate(AdminResourceWrite):
    """ResourceCreate"""

    translations: list[AdminTranslationInput] = Field(..., min_length=1, description="Localized content")


class AdminResourceUpdate(AdminResourceWrite):
    """ResourceUpdate"""


class AdminResourceChangeParent(BaseModel):
    """ResourceChangeParent"""
    pid: UUID = Field(..., description="New parent resource ID")


class AdminResourceBulkDelete(BaseModel):
    """ResourceBulkDelete"""
    ids: list[UUID] = Field(..., description="Resource IDs to delete")


class AdminResourceChangeSequence(ChangeSequence):
    """ResourceChangeSequence"""
