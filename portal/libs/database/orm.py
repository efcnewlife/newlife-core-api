"""
ModelBase class for SQLAlchemy ORM
"""
import re
import uuid
from typing import Optional, Tuple

import sqlalchemy as sa
from sqlalchemy import Column, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

from portal.config import settings

_MODELS_MODULE_ANCHOR = "portal.models"


def _pascal_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _resolve_schema(module_name: str, class_schema: Optional[str]) -> str:
    if class_schema:
        return class_schema

    parts = module_name.split(".")
    anchor_parts = _MODELS_MODULE_ANCHOR.split(".")
    anchor_len = len(anchor_parts)
    for idx in range(len(parts) - anchor_len + 1):
        if parts[idx : idx + anchor_len] == anchor_parts:
            if len(parts) > idx + anchor_len:
                return parts[idx + anchor_len]
            break

    return settings.DATABASE_SCHEMA


def split_schema_and_tablename(class_name: str, module_name: str, class_schema: Optional[str] = None) -> Tuple[str, str]:
    """
    Map ORM class name to (schema, table_name).

    Resolution order:
    1) class explicit schema (cls.__schema__)
    2) module path schema under portal.models.<schema>.*
    3) legacy fallback settings.DATABASE_SCHEMA
    """
    schema = _resolve_schema(module_name, class_schema)
    table = _pascal_to_snake(class_name)
    schema_prefix = f"{schema}_"
    if table.startswith(schema_prefix):
        return schema, table[len(schema_prefix) :]
    return schema, table


def merge_table_args(*args) -> Optional[tuple]:
    """

    :param args:
    :return:
    """
    constraints = []
    kw = {}
    for part in args:
        if not part:
            continue
        if isinstance(part, dict):
            kw.update(part)
        elif isinstance(part, tuple):
            for elem in part:
                if isinstance(elem, dict):
                    kw.update(elem)
                else:
                    constraints.append(elem)
        else:
            constraints.append(part)
    if not constraints and not kw:
        return None
    return (*constraints, kw) if kw else tuple(constraints)


class Base(DeclarativeBase):
    """Base"""
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item)

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Table name is snake_case class name.
        If it starts with "<schema>_", that prefix is removed.
        """
        _, table = split_schema_and_tablename(
            class_name=cls.__name__,
            module_name=cls.__module__,
            class_schema=getattr(cls, "__schema__", None),
        )
        return table

    @declared_attr
    def __table_args__(cls) -> Optional[tuple]:
        """

        :return:
        """
        schema, _ = split_schema_and_tablename(
            class_name=cls.__name__,
            module_name=cls.__module__,
            class_schema=getattr(cls, "__schema__", None),
        )
        base_args = {"schema": schema}
        extra_args = getattr(cls, "__extra_table_args__", None)
        return merge_table_args(base_args, extra_args)


class ModelBase(Base):
    """ModelBase"""
    __abstract__ = True
    id = Column(UUID, server_default=sa.text("uuidv7()"), primary_key=True, comment="Primary Key")

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
