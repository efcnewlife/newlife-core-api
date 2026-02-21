"""
ModelBase class for SQLAlchemy ORM
"""
import re
import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Column, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

from portal.config import settings


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
        schema=settings.DATABASE_SCHEMA,
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_N_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
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
        Snake case table name based on class name
        e.g., MyModel -> my_model
        :return:
        """
        name = cls.__name__
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return snake

    @declared_attr
    def __table_args__(cls) -> Optional[tuple]:
        """

        :return:
        """
        base_args = {"schema": settings.DATABASE_SCHEMA}
        extra_args = getattr(cls, "__extra_table_args__", None)
        return merge_table_args(base_args, extra_args)


class ModelBase(Base):
    """ModelBase"""
    __abstract__ = True
    id = Column(UUID, server_default=sa.text("gen_random_uuid()"), primary_key=True, comment="Primary Key")

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
