"""
JWT Provider for DI
"""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

import jwt

from portal.config import settings
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.consts.permission import Verb
from portal.libs.logger import logger
from portal.providers.token_blacklist_provider import TokenBlacklistProvider
from portal.application.auth.results import AccessTokenPayload, UserSensitive

VERB_SET = {Verb.READ.value, Verb.CREATE.value, Verb.UPDATE.value, Verb.DELETE.value}


class JWTProvider:
    """JWT Token Provider"""

    def __init__(self, token_blacklist_provider: TokenBlacklistProvider):
        self.token_blacklist_provider = token_blacklist_provider
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        self._issuer = settings.BASE_URL
        self._audience = settings.APP_NAME

    @staticmethod
    def _generate_scope(permissions: list[str] = None) -> str:
        """
        Generate scope from permissions
        If the permission includes all verbs, return "resource:*"
        If the permission includes specific verbs, return "resource:verb1,resource:verb2"
        Example: ["system:user:read", "system:user:create", "system:user:modify", "system:user:delete", "system:role:read"]
        scope: "system:user:* system:role:read"
        :param permissions:
        :return:
        """
        if not permissions:
            return ""
        resource_verb_map = defaultdict(set)
        for permission in permissions:
            # parse permission like "system:user:read"
            resource, verb = permission.rsplit(":", 1)
            if resource not in resource_verb_map:
                resource_verb_map[resource] = set()
            resource_verb_map[resource].add(verb)
        scope = []
        for resource, verbs in resource_verb_map.items():  # type: (str, set)
            if verbs == VERB_SET:
                scope.append(f"{resource}:*")
            else:
                scope.extend([f"{resource}:{verb}" for verb in verbs])
        return " ".join(scope)

    def create_access_token(
        self,
        user: UserSensitive,
        family_id: UUID,
        roles: list = None,
        permissions: list = None,
        aud_type: AccessTokenAudType = AccessTokenAudType.USER,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """

        :param user:
        :param family_id:
        :param roles:
        :param permissions:
        :param aud_type:
        :param expires_delta:
        :return:
        """
        now = datetime.now(timezone.utc)
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=self.access_token_expire_minutes)

        access_token_payload = None
        match aud_type:
            case AccessTokenAudType.ADMIN:
                access_token_payload = AccessTokenPayload(
                    iss=self._issuer,
                    exp=int(expire.timestamp()),
                    sub=user.id,
                    aud=self._audience + "-admin",
                    iat=int(now.timestamp()),
                    user_id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    roles=roles,
                    scope=self._generate_scope(permissions=permissions),
                    family_id=family_id
                )
            case AccessTokenAudType.USER:
                access_token_payload = AccessTokenPayload(
                    iss=self._issuer,
                    exp=int(expire.timestamp()),
                    sub=user.id,
                    aud=self._audience,
                    iat=int(now.timestamp()),
                    user_id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    preferred_name=user.preferred_name,
                    family_id=family_id
                )
            case _:
                raise ValueError(f"Invalid access token aud type: {aud_type}")
        if not access_token_payload:
            raise ValueError("Invalid access token payload")
        encoded_jwt = jwt.encode(
            access_token_payload.model_dump(mode="json", exclude_none=True),
            self.secret_key,
            algorithm=self.algorithm,
        )
        return encoded_jwt

    def verify_token(self, token: str, is_admin: bool = True, **kwargs) -> Optional[AccessTokenPayload]:
        """
        Verify and decode token
        :param token:
        :param is_admin:
        :param kwargs:
        :return:
        """
        try:
            audience = self._audience + "-app" if not is_admin else self._audience + "-admin"
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience=audience,
                issuer=self._issuer,
                **kwargs
            )
            return AccessTokenPayload.model_validate(payload)
        except jwt.PyJWTError as e:
            logger.error(f"Error decoding JWT: {e}")
            return None
