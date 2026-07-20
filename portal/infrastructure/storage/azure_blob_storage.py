"""
Azure Blob Storage adapter implementing FileStoragePort.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from azure.core.exceptions import AzureError
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from portal.config import Configuration, settings
from portal.libs.logger import logger


class AzureBlobStorage:
    """Azure Blob object storage."""

    def __init__(self, config: Optional[Configuration] = None):
        self._config = config or settings
        self._connection_string = self._config.AZURE_STORAGE_CONNECTION_STRING
        self._account_name = self._config.AZURE_STORAGE_ACCOUNT_NAME
        self._container_name = self._config.AZURE_STORAGE_CONTAINER_NAME
        self._region = self._config.AZURE_STORAGE_REGION
        self._prefix = self._config.AZURE_STORAGE_BLOB_PREFIX
        self._cache_control = self._config.AZURE_BLOB_CACHE_CONTROL
        self._client: Optional[BlobServiceClient] = None
        self._account_key: Optional[str] = None

        if self._connection_string:
            self._client = BlobServiceClient.from_connection_string(self._connection_string)
            self._account_name = self._client.account_name
            self._account_key = self._parse_account_key(self._connection_string)

    @staticmethod
    def _parse_account_key(connection_string: str) -> Optional[str]:
        for part in connection_string.split(";"):
            if part.startswith("AccountKey="):
                return part[len("AccountKey="):]
        return None

    @property
    def storage_name(self) -> str:
        return "azure_blob"

    @property
    def bucket(self) -> str:
        return self._container_name

    @property
    def region(self) -> str:
        return self._region

    @property
    def blob_prefix(self) -> str:
        return self._prefix

    def _ensure_client(self) -> BlobServiceClient:
        if self._client is None:
            raise AzureError("Azure Blob Storage is not configured (missing connection string)")
        return self._client

    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        metadata: dict[str, str],
        cache_control: Optional[str] = None,
    ) -> None:
        client = self._ensure_client()
        blob_client = client.get_blob_client(container=self._container_name, blob=key)
        content_settings = ContentSettings(
            content_type=content_type,
            cache_control=cache_control or self._cache_control,
        )

        def _upload() -> None:
            blob_client.upload_blob(
                body,
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata,
            )

        await asyncio.to_thread(_upload)

    async def delete_objects(self, keys: list[str]) -> list[str]:
        if not keys:
            return []
        client = self._ensure_client()
        container_client = client.get_container_client(self._container_name)
        success_keys: list[str] = []

        def _delete() -> list[str]:
            deleted: list[str] = []
            for key in keys:
                try:
                    container_client.delete_blob(key)
                    deleted.append(key)
                except AzureError as exc:
                    logger.warning("Failed to delete blob key=%s: %s", key, exc)
            return deleted

        success_keys = await asyncio.to_thread(_delete)
        return success_keys

    async def generate_signed_read_url(
        self,
        *,
        key: str,
        bucket: Optional[str] = None,
        expiry_seconds: int = 3600,
    ) -> str:
        client = self._ensure_client()
        container = bucket or self._container_name
        account_name = self._account_name or client.account_name
        if not account_name or not self._account_key:
            raise AzureError("Cannot generate SAS URL without account name and key")

        def _generate() -> str:
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container,
                blob_name=key,
                account_key=self._account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(seconds=expiry_seconds),
            )
            encoded_key = quote(key, safe="/")
            return (
                f"https://{account_name}.blob.core.windows.net/"
                f"{container}/{encoded_key}?{sas_token}"
            )

        return await asyncio.to_thread(_generate)
