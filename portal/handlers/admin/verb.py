"""
AdminVerbHandler
"""
from typing import Optional

import sqlalchemy as sa
from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys, CacheExpiry
from portal.libs.contexts.request_context import get_request_context, RequestContext
from portal.libs.database import Session, RedisPool
from portal.models import AuthVerb, AuthVerbTranslation
from portal.serializers.admin.v1.verb import AdminVerbList, AdminVerbItem


class AdminVerbHandler:
    """AdminVerbHandler"""

    def __init__(
        self,
        session: Session,
        redis_client: RedisPool,
    ):
        self._session = session
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._req_ctx: Optional[RequestContext] = get_request_context()

    async def get_verb_list(self) -> AdminVerbList:
        """

        :return:
        """
        if not (self._req_ctx and self._req_ctx.resolved_locale_id):
            return AdminVerbList(items=[])
        loc_id = self._req_ctx.resolved_locale_id
        cache_key = CacheKeys(resource="verb").add_attribute("list").add_attribute(str(loc_id)).build()
        cached = await self._redis.get(cache_key)
        if cached:
            return AdminVerbList.model_validate_json(cached)
        verbs: list[AdminVerbItem] = await (
            self._session.select(
                AuthVerb.id,
                AuthVerb.action,
                AuthVerbTranslation.name,
                AuthVerbTranslation.description,
            )
            .select_from(AuthVerb)
            .join(
                AuthVerbTranslation,
                sa.and_(
                    AuthVerbTranslation.verb_id == AuthVerb.id,
                    AuthVerbTranslation.locale_id == loc_id,
                ),
            )
            .where(AuthVerb.is_active == True)
            .where(AuthVerb.is_deleted == False)
            .order_by(AuthVerb.created_at)
            .fetch(as_model=AdminVerbItem)
        )
        if not verbs:
            return AdminVerbList(items=[])
        result = AdminVerbList(items=verbs)
        await self._redis.set(
            cache_key,
            result.model_dump_json(),
            ex=CacheExpiry.MONTH,
        )
        return result
