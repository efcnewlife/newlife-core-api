"""
Model for Mixins (backward-compatible re-exports).
"""
from portal.serializers.mixins.model_mixins import (
    AuditMixinModel,
    BaseMixinModel,
    DeleteMixinModel,
    DescriptionMixinModel,
    JSONStringMixinModel,
    RemarkMixinModel,
    SortableMixinModel,
    UUIDBaseModel,
)

__all__ = [
    "UUIDBaseModel",
    "JSONStringMixinModel",
    "SortableMixinModel",
    "AuditMixinModel",
    "DeleteMixinModel",
    "DescriptionMixinModel",
    "RemarkMixinModel",
    "BaseMixinModel",
]
