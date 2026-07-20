"""
File validation dependencies.
"""
from fastapi import UploadFile

from portal.config import settings
from portal.exceptions.responses import BadRequestException, EntityTooLargeException


class FileValidation:
    """Validate upload size and content type."""

    def __init__(self, allowed_types: list[str]):
        self.allowed_types = allowed_types

    def __call__(self, file: UploadFile) -> UploadFile:
        content_length = file.size
        if content_length and content_length > settings.MAX_UPLOAD_SIZE:
            raise EntityTooLargeException()
        if file.content_type not in self.allowed_types:
            raise BadRequestException(
                detail=(
                    f"File type {file.content_type} is not allowed. "
                    f"Allowed types: {', '.join(self.allowed_types)}"
                )
            )
        return file
