"""
MSGraphUsers — Microsoft Graph users directory reads (beta).
"""
from collections.abc import AsyncIterator
from typing import Optional, Type

from kiota_abstractions.serialization import Parsable
from msgraph_beta.generated.models.o_data_errors.o_data_error import ODataError
from msgraph_beta.generated.models.user import User
from msgraph_beta.generated.models.user_collection_response import UserCollectionResponse
from msgraph_beta.generated.users.users_request_builder import UsersRequestBuilder

from portal.libs.logger import logger
from portal.providers.ms_graph.base import MSGraphClientBase
from portal.providers.ms_graph.models import GraphUserRecord

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


class MSGraphUsers(MSGraphClientBase):
    """Fetch users from Microsoft Graph using app-only credentials."""

    @staticmethod
    def _parse_user(user: User) -> Optional[GraphUserRecord]:
        object_id = str(user.id or "").strip()
        if not object_id:
            return None
        return GraphUserRecord(
            object_id=object_id,
            email=(user.mail or None),
            given_name=(user.given_name or None),
            surname=(user.surname or None),
            display_name=(user.display_name or None),
            account_enabled=bool(user.account_enabled if user.account_enabled is not None else True),
            user_principal_name=(user.user_principal_name or None),
            user_type=(user.user_type or None),
        )

    def _users_request_configuration(
        self,
        *,
        include_query_parameters: bool = True,
    ) -> UsersRequestBuilder.UsersRequestBuilderGetRequestConfiguration:
        request_configuration = UsersRequestBuilder.UsersRequestBuilderGetRequestConfiguration(
            options=self.configuration.options,
            query_parameters=(
                self.configuration.query_parameters if include_query_parameters else None
            ),
        )
        self._apply_headers(request_configuration)
        return request_configuration

    async def get_users(self) -> UserCollectionResponse:
        """Fetch the first page of users with current configuration."""
        if not self.is_configured():
            raise RuntimeError("Microsoft Graph is not configured")
        try:
            request_configuration = self._users_request_configuration()
            result = await self.client.users.get(request_configuration=request_configuration)
            if result is None:
                return UserCollectionResponse(value=[])
            return result
        except ODataError as exc:
            logger.error(
                "Graph users request failed: code=%s message=%s",
                getattr(exc.error, "code", None) if getattr(exc, "error", None) else None,
                getattr(exc.error, "message", None) if getattr(exc, "error", None) else str(exc),
            )
            raise

    async def get_next_link(
        self,
        next_link: str,
        parser: Type[Parsable] = UserCollectionResponse,
    ) -> UserCollectionResponse:
        """Follow an @odata.nextLink URL for users pagination."""
        if not self.is_configured():
            raise RuntimeError("Microsoft Graph is not configured")
        try:
            request_configuration = self._users_request_configuration(
                include_query_parameters=False,
            )
            request_info = self.client.users.to_get_request_information(
                request_configuration=request_configuration,
            )
            request_info.url = next_link
            item = await self.client.users.request_adapter.send_async(
                request_info,
                parser,
                self.default_error,
            )
            if item is None:
                return UserCollectionResponse(value=[])
            return item
        except ODataError as exc:
            logger.error(
                "Graph users nextLink request failed: code=%s message=%s",
                getattr(exc.error, "code", None) if exc.error else None,
                getattr(exc.error, "message", None) if getattr(exc, "error", None) else str(exc),
            )
            raise

    async def list_users(
        self,
        *,
        filter_expr: str,
        select_fields: Optional[list[str]] = None,
        page_size: int = 999,
    ) -> AsyncIterator[GraphUserRecord]:
        """
        Yield users from Graph with pagination via odata_next_link.
        """
        if not self.is_configured():
            raise RuntimeError("Microsoft Graph is not configured")

        selected = select_fields or DEFAULT_USER_SELECT_FIELDS
        query_parameter = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            count=True,
            filter=filter_expr,
            select=selected,
            top=page_size,
        )
        self.add_header(key="ConsistencyLevel", value="eventual")
        self.add_query_parameter(query_parameter)

        page = await self.get_users()
        while True:
            for user in page.value or []:
                record = self._parse_user(user)
                if record:
                    yield record

            next_link = page.odata_next_link
            if not next_link:
                break
            page = await self.get_next_link(next_link)
