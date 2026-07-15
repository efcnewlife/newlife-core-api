"""
Microsoft Graph API client for app-only directory reads (beta endpoint).
"""
import asyncio
from collections.abc import AsyncIterator
from typing import Any, Optional

import httpx
import msal
from pydantic import BaseModel, Field

from portal.config import settings
from portal.libs.logger import logger

GRAPH_BASE_URL = "https://graph.microsoft.com/beta"
GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
DEFAULT_USER_SELECT_FIELDS = [
    "id",
    "displayName",
    "userPrincipalName",
    "mail",
    "givenName",
    "surname",
    "accountEnabled",
    "userType",
]


class GraphUserRecord(BaseModel):
    """Normalized Graph user fields for directory sync."""

    object_id: str = Field(..., description="Entra object id")
    email: Optional[str] = None
    given_name: Optional[str] = None
    surname: Optional[str] = None
    display_name: Optional[str] = None
    account_enabled: bool = True
    user_principal_name: Optional[str] = None
    user_type: Optional[str] = None


class MicrosoftGraphProvider:
    """Fetch users from Microsoft Graph using client credentials."""

    def __init__(self) -> None:
        self._tenant_id = settings.AZURE_TENANT_ID
        self._client_id = settings.AZURE_APP_CLIENT_ID
        self._client_secret = settings.AZURE_APP_CLIENT_SECRET
        self._msal_app: Optional[msal.ConfidentialClientApplication] = None
        if self._tenant_id and self._client_id and self._client_secret:
            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._client_id,
                client_credential=self._client_secret,
                authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            )

    def is_configured(self) -> bool:
        return self._msal_app is not None

    def _acquire_access_token(self) -> str:
        if not self._msal_app:
            raise RuntimeError("Microsoft Graph is not configured")
        result = self._msal_app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if not result or "access_token" not in result:
            error_description = (result or {}).get("error_description") or (result or {}).get("error")
            raise RuntimeError(f"Failed to acquire Graph access token: {error_description}")
        return str(result["access_token"])

    async def _get_access_token(self) -> str:
        return await asyncio.to_thread(self._acquire_access_token)

    @staticmethod
    def _parse_user(raw: dict[str, Any]) -> Optional[GraphUserRecord]:
        object_id = str(raw.get("id") or "").strip()
        if not object_id:
            return None
        return GraphUserRecord(
            object_id=object_id,
            email=(raw.get("mail") or None),
            given_name=(raw.get("givenName") or None),
            surname=(raw.get("surname") or None),
            display_name=(raw.get("displayName") or None),
            account_enabled=bool(raw.get("accountEnabled", True)),
            user_principal_name=(raw.get("userPrincipalName") or None),
            user_type=(raw.get("userType") or None),
        )

    async def list_users(
        self,
        *,
        filter_expr: str,
        select_fields: Optional[list[str]] = None,
        page_size: int = 999,
    ) -> AsyncIterator[GraphUserRecord]:
        """
        Yield users from Graph with pagination via @odata.nextLink.
        """
        if not self.is_configured():
            raise RuntimeError("Microsoft Graph is not configured")

        access_token = await self._get_access_token()
        selected = select_fields or DEFAULT_USER_SELECT_FIELDS
        params: dict[str, str] = {
            "$filter": filter_expr,
            "$select": ",".join(selected),
            "$top": str(page_size),
            "$count": "true",
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "ConsistencyLevel": "eventual",
        }
        next_url: Optional[str] = f"{GRAPH_BASE_URL}/users"
        next_params: Optional[dict[str, str]] = params

        async with httpx.AsyncClient(timeout=60.0) as client:
            while next_url:
                response = await client.get(
                    next_url,
                    headers=headers,
                    params=next_params,
                )
                if response.status_code >= 400:
                    logger.error(
                        "Graph users request failed: status=%s body=%s",
                        response.status_code,
                        response.text,
                    )
                    response.raise_for_status()

                payload = response.json()
                for raw_user in payload.get("value") or []:
                    record = self._parse_user(raw_user)
                    if record:
                        yield record

                next_url = payload.get("@odata.nextLink")
                next_params = None
