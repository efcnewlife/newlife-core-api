"""
Configuration - Template
"""
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional, Any, Type, Tuple

import yaml
from dotenv import load_dotenv
from pydantic import model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, PydanticBaseSettingsSource

from portal.libs.shared import Converter
from portal.libs.rate_limit.config import RateLimitersConfig

load_dotenv()


class CustomSource(EnvSettingsSource):

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool
    ) -> Any:
        """
        Prepare field value for custom source.
        """
        if field.annotation is bool:
            return Converter.to_bool(value, default=field.default or False)
        if isinstance(list[str], type(field.annotation)):
            return [v for v in value.split(',')]
        return value


class Configuration(BaseSettings):
    """
    Configuration - Template
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (CustomSource(settings_cls),)

    # [App Base]
    APP_NAME: str = "newlife-core-api"
    ENV: str = os.getenv(key="ENV", default="dev").lower()
    APP_VERSION: str = os.getenv(key="VERSION", default="v0.1.0")
    IS_PROD: bool = ENV == "prod"
    IS_DEV: bool = ENV not in ["prod", "stg"]
    APP_FQDN: str = os.getenv(key="APP_FQDN", default="localhost")
    BASE_URL: str = f"https://{APP_FQDN}" if IS_PROD else f"http://{APP_FQDN}"
    ADMIN_PORTAL_URL: str = os.getenv(key="ADMIN_PORTAL_URL", default="http://localhost:5173")
    DEFAULT_LOCALE: str = os.getenv(key="DEFAULT_LOCALE", default="en")

    # [FastAPI]
    HOST: str = os.getenv(key="HOST", default="127.0.0.1")
    PORT: int = os.getenv(key="PORT", default=8000)
    DOCS_BASIC_AUTH_USERNAME: str = os.getenv(key="DOCS_BASIC_AUTH_USERNAME", default="developer")
    DOCS_BASIC_AUTH_PASSWORD: str = os.getenv(key="DOCS_BASIC_AUTH_PASSWORD", default="developer")

    # [CORS]
    CORS_ALLOWED_ORIGINS: list[str] = os.getenv(key="CORS_ALLOWED_ORIGINS", default="*").split()
    CORS_ALLOW_ORIGINS_REGEX: Optional[str] = os.getenv(key="CORS_ALLOW_ORIGINS_REGEX")

    # [STORAGE]
    # TODO: Add support for S3, Azure Blob Storage, etc.
    MAX_UPLOAD_SIZE: int = int(os.getenv(key="MAX_UPLOAD_SIZE", default=5 * 1024 * 1024))  # 3MB

    # [Redis]
    REDIS_URL: Optional[str] = os.getenv(key="REDIS_URL")
    REDIS_DB: int = int(os.getenv(key="REDIS_DB", default="0"))
    RATE_LIMITER_REDIS_DB: int = int(os.getenv(key="RATE_LIMITER_REDIS_DB", default="10"))

    # [Database]
    DATABASE_HOST: str = os.getenv(key="DATABASE_HOST", default="localhost")
    DATABASE_USER: str = os.getenv(key="DATABASE_USER", default="postgres")
    DATABASE_PASSWORD: str = os.getenv(key="DATABASE_PASSWORD", default="")
    DATABASE_PORT: str = os.getenv(key="DATABASE_PORT", default="5432")
    DATABASE_NAME: str = os.getenv(key="DATABASE_NAME", default="postgres")
    DATABASE_SCHEMA: str = os.getenv(key="DATABASE_SCHEMA", default="public")
    DATABASE_CONNECTION_POOL_MAX_SIZE: int = os.getenv("DATABASE_CONNECTION_POOL_MAX_SIZE", 10)
    DATABASE_APPLICATION_NAME: str = APP_NAME

    DATABASE_POOL: bool = os.getenv("DATABASE_POOL", True)
    SQL_ECHO: bool = os.getenv("SQL_ECHO", False)
    SQLALCHEMY_DATABASE_URI: str = f'postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}'
    ASYNC_DATABASE_URL: str = f'postgresql+asyncpg://{DATABASE_USER}:{DATABASE_PASSWORD}@' \
                              f'{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}'

    # [JWT]
    JWT_SECRET_KEY: str = os.getenv(key="JWT_SECRET_KEY", default="change-me-in-production")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv(key="JWT_ACCESS_TOKEN_EXPIRE_MINUTES", default="15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv(key="REFRESH_TOKEN_EXPIRE_DAYS", default="7"))
    REFRESH_TOKEN_HASH_SALT: str = os.getenv(key="REFRESH_TOKEN_HASH_SALT", default="")
    REFRESH_TOKEN_HASH_PEPPER: str = os.getenv(key="REFRESH_TOKEN_HASH_PEPPER", default="")

    # [Microsoft Entra ID — Admin Portal SPA token exchange]
    AZURE_TENANT_ID: Optional[str] = os.getenv(key="AZURE_TENANT_ID", default=None)
    AZURE_APP_CLIENT_ID: Optional[str] = os.getenv(key="AZURE_APP_CLIENT_ID", default=None)
    AZURE_APP_CLIENT_SECRET: Optional[str] = os.getenv(key="AZURE_APP_CLIENT_SECRET", default=None)
    AZURE_ALLOWED_ISSUERS: Optional[str] = os.getenv(key="AZURE_ALLOWED_ISSUERS", default=None)

    # [Token Blacklist]
    TOKEN_BLACKLIST_REDIS_DB: int = int(os.getenv(key="TOKEN_BLACKLIST_REDIS_DB", default="1"))
    TOKEN_BLACKLIST_CLEANUP_INTERVAL: int = int(os.getenv(key="TOKEN_BLACKLIST_CLEANUP_INTERVAL", default="3600"))

    # [Rate Limiting]
    RATE_LIMITERS_CONFIG: Optional[RateLimitersConfig] = None

    # [Logging]
    SENSITIVE_PARAMS: set[str] = set(os.getenv(key="SENSITIVE_PARAMS", default="password,secret,api_key").split(","))

    @model_validator(mode="after")
    def _load_rate_limiters_config(self) -> "Configuration":
        """Load rate limiters configuration from YAML file."""
        if self.RATE_LIMITERS_CONFIG:
            return self

        candidate_paths: list[str] = []
        rate_limiters_config_path = os.getenv(key="RATE_LIMITERS_CONFIG_PATH")
        if rate_limiters_config_path:
            candidate_paths.append(rate_limiters_config_path)

        project_dir = Path(__file__).resolve().parent.parent
        candidate_paths.extend(
            [
                os.path.join(project_dir, "env/rate_limiters.yaml"),
                "/etc/secrets/rate_limiters.yaml",
            ]
        )

        for candidate_path in candidate_paths:
            try:
                rate_limiters_path: Path = Path(candidate_path)
                if rate_limiters_path.exists():
                    config_dict = yaml.safe_load(rate_limiters_path.read_text())
                    self.RATE_LIMITERS_CONFIG = RateLimitersConfig(**config_dict)
                    logger = logging.getLogger(self.APP_NAME)
                    logger.info(f"Rate limiters config loaded from {candidate_path}")
                    break
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger = logging.getLogger(self.APP_NAME)
                logger.warning(f"Failed to load rate limiters config from {candidate_path}: {exc}")

        if not self.RATE_LIMITERS_CONFIG:
            logger = logging.getLogger(self.APP_NAME)
            logger.warning("Rate limiters config not found, using default values")
            default_config_dict = {
                "default": {
                    "short": {"times": 10, "seconds": 1},
                    "medium": {"times": 50, "seconds": 30},
                    "long": {"times": 1000, "seconds": 3600},
                },
                "read": {
                    "short": {"times": 20, "seconds": 1},
                    "medium": {"times": 100, "seconds": 30},
                    "long": {"times": 1800, "seconds": 3600},
                },
                "write": {
                    "short": {"times": 10, "seconds": 1},
                    "medium": {"times": 60, "seconds": 30},
                    "long": {"times": 1200, "seconds": 3600},
                }
            }
            self.RATE_LIMITERS_CONFIG = RateLimitersConfig(**default_config_dict)

        return self

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() == "prod"

    @property
    def is_dev(self) -> bool:
        return self.ENV.lower() not in ("prod", "stg")


@lru_cache()
def get_settings() -> Configuration:
    return Configuration()


settings: Configuration = get_settings()
