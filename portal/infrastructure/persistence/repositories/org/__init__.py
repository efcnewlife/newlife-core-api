"""Organization repositories."""

from .ministry_repository import MinistryRepository
from .ministry_type_repository import MinistryTypeRepository
from .position_repository import PositionRepository
from .target_audience_repository import TargetAudienceRepository

__all__ = [
    "MinistryRepository",
    "MinistryTypeRepository",
    "TargetAudienceRepository",
    "PositionRepository",
]
