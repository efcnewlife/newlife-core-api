import asyncio
import inspect
import re
import uuid
from datetime import datetime, date
from enum import Enum, StrEnum
from typing import List, Callable, overload, Tuple, Union, TypeVar, Type, Any, Optional

import asyncpg
import sqlalchemy as sa
from asyncpg import Record
from asyncpg.transaction import TransactionState
from pydantic import BaseModel
from sqlalchemy import String, Numeric, Integer, Float, Boolean, DateTime, Date, ColumnExpressionArgument, Column
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql.dml import Insert as PgInsert
from sqlalchemy.dialects.postgresql.base import PGCompiler
from sqlalchemy.orm import Query, aliased
from sqlalchemy.sql import FromClause
from sqlalchemy.sql.dml import Update, Delete, Insert
from sqlalchemy.sql.selectable import ScalarSelect

from portal.config import settings
from portal.libs.database.aio_pg import PostgresConnection, ConnectionType
from portal.libs.database.orm import Base, ModelBase
from portal.libs.logger import logger
from portal.libs.shared import Converter, Assert, validator

dialect = postgresql.dialect()

__all__ = ["ISession", "Session"]

T = TypeVar("T")

TableTypes = Union["Table", Type[sa.Table], Type[Base], Type[ModelBase]]


class FetchMethod(StrEnum):
    """Fetch Method"""
    FETCH = "fetch"
    FETCH_VAL = "fetch_val"
    FETCH_ROW = "fetch_row"


def _format_value(value):
    return Converter.format_value(value)


def _format_dict(item: Record, as_model: Type[BaseModel] = None):
    if item is None:
        return item
    if as_model:
        return as_model.model_validate(dict(item))
    else:
        data = {}
        for name, value in dict(item).items():
            if isinstance(value, list) or isinstance(value, tuple):
                data[name] = [Converter.format_value(item) for item in value]
            else:
                data[name] = Converter.format_value(value)
        return data


def _format_where(clauses: tuple) -> Union[tuple, ColumnExpressionArgument]:
    Assert.is_not_null(clauses, "clauses")
    if len(clauses) > 2:
        raise TypeError(
            "There are too many where condition parameters, "
            "please use multiple where for multiple conditions or "
            "use or_, and_ for splicing"
        )
    if len(clauses) == 2:
        where_clause = condition_clause(clauses[0], clauses[1])
    else:
        where_clause = clauses[0]
    return where_clause

def _get_order_by(
    tables: Union[Type, List[Type], None],
    order_by: str,
    descending=True,
    **map_columns
):
    """
    获取排序字段
    :param tables:
    :param order_by:
    :param descending:
    :return:
    """
    col: Optional[Column] = None
    ordered_items = []
    if not isinstance(tables, list):
        tables = [tables]
    if order_by:
        if map_columns and order_by in map_columns:
            column = map_columns[order_by]
            if isinstance(column, tuple):
                _col, action = column
                if action == "nulls":
                    if descending:
                        ordered_items.append(sa.sql.expression.nullslast(_col.desc()))
                    else:
                        ordered_items.append(sa.sql.expression.nullsfirst(_col))
            else:
                col = column
        else:
            for table in tables:
                if hasattr(table, order_by):
                    col = getattr(table, order_by)
                    break
    if not tables and not map_columns:
        raise ValueError("Table and map_columns cannot be empty at the same time")
    if col is None and not ordered_items:
        descending = True
        if hasattr(tables[0], "sequence"):
            col = getattr(tables[0], "sequence")
        else:
            col = getattr(tables[0], "created_at")

    if col is not None:
        if descending:
            if isinstance(col, str):
                ordered_items.append(f"{col} desc")
            else:
                ordered_items.append(col.desc())
        else:
            ordered_items.append(col)
    if "id" not in ordered_items and hasattr(tables[0], "id"):
        ordered_items.append(getattr(tables[0], "id"))
    return ordered_items



class _Insert:
    def __init__(self, insert: PgInsert, session: "Session"):
        self._insert = insert
        self._session = session

    def values(self, *args, **kwargs):
        """
        :rtype: _Insert
        """
        if args and len(args) == 1:
            if isinstance(args[0], dict):
                self._insert = self._insert.values(**args[0], **kwargs)
                return self
        self._insert = self._insert.values(*args, **kwargs)
        return self

    def excluded(self):
        self._insert = self._insert.excluded()
        return self

    def on_conflict_do_nothing(self, constraint=None, index_elements=None, index_where=None):
        self._insert = self._insert.on_conflict_do_nothing(
            constraint=constraint,
            index_elements=index_elements,
            index_where=index_where
        )
        return self

    def on_conflict_do_update(
        self,
        constraint=None,
        index_elements=None,
        index_where=None,
        set_=None,
        where=None
    ):
        self._insert = self._insert.on_conflict_do_update(
            constraint=constraint,
            index_elements=index_elements,
            index_where=index_where,
            set_=set_,
            where=where
        )
        return self

    async def execute(self):
        return await self._session.execute(self._insert)

    def __str__(self):
        return str(self._insert.compile(dialect=postgresql.dialect()))


class _Update:
    def __init__(self, update: Update, session: "Session"):
        self._update = update
        self._session = session

    @overload
    def where(self, where_clause):
        """
        :rtype: _Update
        """
        pass

    @overload
    def where(self, conditional_exp: callable, where_clause):
        """
        :rtype: _Update
        """
        pass

    def where(self, *clauses):
        """
        :rtype: _Update
        """
        where_clause = _format_where(clauses)
        if where_clause is not None:
            self._update = self._update.where(where_clause)
        return self

    def values(self, *args, **kwargs):
        """
        :rtype: _Update
        """
        if args and len(args) == 1:
            if isinstance(args[0], dict):
                self._update = self._update.values(**args[0])
                return self
        self._update = self._update.values(*args, **kwargs)
        return self

    async def execute(self):
        return await self._session.execute(self._update)

    def __str__(self):
        return str(self._update)


class _Select:
    def __init__(self, columns, mclass: Type[T], session: "Session"):
        self._select = Query(columns)
        self._mclass = mclass
        self._session = session  # type:Session
        # self._query = None

    @overload
    def where(self, where_clause) -> "_Select":
        """
        :rtype: _Select
        """
        pass

    @overload
    def where(self, conditional_exp, where_clause) -> "_Select":
        """
        :param conditional_exp:
        :param where_clause:
        :return:
        """
        pass

    def where(self, *clauses) -> "_Select":
        """
        :rtype: _Select
        """
        where_clause = _format_where(clauses)
        if where_clause is not None:
            self._select = self._select.filter(where_clause)
        return self

    def join(
        self,
        right: Union[FromClause, sa.Table],
        onclause: Optional[FromClause] = None,
        full: bool = False
    ):
        if onclause is None:
            self._select = self._select.join(right, full=full)
        else:
            self._select = self._select.join(right, onclause, full=full)
        return self

    def outerjoin(
        self,
        right: Union[FromClause, sa.Table],
        onclause: Optional[FromClause] = None,
        full: bool = False
    ):
        """
        :param right:
        :param onclause:
        :param full:
        :return:
        """
        if onclause is None:
            self._select = self._select.outerjoin(right, full=full)
        else:
            self._select = self._select.outerjoin(right, onclause, full=full)
        return self

    def dynamic_join(
        self,
        condition: Union[Callable, bool],
        right: Union[FromClause, sa.Table],
        onclause: Optional[FromClause] = None,
        full: bool = False
    ):
        """
        :param full:
        :param onclause:
        :param right:
        :param condition:
        :return:
        """
        if condition is None or condition is False:
            return self
        if callable(condition):
            ret = condition()
            if ret is None or ret is False:
                return self
        return self.join(right, onclause, full=full)

    def dynamic_outerjoin(
        self,
        condition: Union[Callable, bool],
        right: Union[FromClause, sa.Table],
        onclause: Optional[FromClause] = None,
        full: bool = False
    ):
        """
        :param condition:
        :param right:
        :param onclause:
        :param full:
        :return:
        """
        if condition is None or condition is False:
            return self
        if callable(condition):
            ret = condition()
            if ret is None or ret is False:
                return self
        return self.outerjoin(right, onclause, full=full)

    def select_from(self, *from_obj):
        """
        :rtype:_Select
        """
        self._select = self._select.select_from(*from_obj)
        return self

    @overload
    def order_by(self, conditional_exp: bool, where_clause):
        """
        :rtype: _Select
        """
        pass

    def order_by(self, *clauses):
        """
        :param clauses:
        :return:
        :rtype:_Select
        """
        if not clauses:
            return self
        if len(clauses) > 2:
            raise TypeError("Too many order_by parameters")
        if len(clauses) == 2 and callable(clauses[1]):
            order_clause = condition_clause(clauses[0], clauses[1])
        else:
            order_clause = clauses[0]
        if order_clause is None:
            return self
        if isinstance(order_clause, list):
            self._select = self._select.order_by(*order_clause)
        else:
            self._select = self._select.order_by(order_clause)
        return self

    def order_by_with(self, tables: Union[Type[sa.Table], List[Type[sa.Table]], None], order_by: str, descending=True, **map_columns):
        """

        :param tables:
        :param descending:
        :param order_by:
        :param map_columns:
        :return:
        :rtype:_Select
        """
        self._select = self._select.order_by(*_get_order_by(tables, order_by=order_by, descending=descending, **map_columns))
        return self

    def group_by(self, *clauses):
        """
        :param clauses:
        :return:
        :rtype:_Select
        """
        self._select = self._select.group_by(*clauses)
        return self

    def distinct(self, *expr):
        """
        :param expr:
        :return:
        :rtype:_Select
        """
        self._select = self._select.distinct(*expr)
        return self

    def having(self, having_clause):
        """
        :param having_clause:
        :return:
        :rtype:_Select
        """
        self._select = self._select.having(having_clause)
        return self

    def offset(self, offset: int):
        """
        :param offset:
        :return:
        :rtype:_Select
        """
        self._select = self._select.offset(offset)
        return self

    def limit(self, limit: int):
        """
        :param limit:
        :return:
        :rtype:_Select
        """
        self._select = self._select.limit(limit)
        return self

    def subquery(self, name: str = None, with_labels=False, reduce_columns=False):
        """
        :rtype:subquery
        """
        return self._select.subquery(name, with_labels=with_labels, reduce_columns=reduce_columns)

    def scalar_subquery(self) -> ScalarSelect:
        """
        :rtype:ScalarSelect
        """
        return self._select.scalar_subquery()

    def cte(self, name: str = None, recursive=False):
        """
        :rtype:_Select
        """
        return self._select.cte(name, recursive=recursive)

    async def fetch(self, as_model: Type[BaseModel] = None) -> List[T]:
        return await self._session.fetch(self._select.statement, as_model=as_model)

    async def fetchgroup(self, groupby: str, as_model: Type[BaseModel] = None):
        """
        :param as_model:
        :param groupby:
        :return:
        """
        return await self._session.fetchgroup(self._select.statement, groupby=groupby, as_model=as_model)

    async def fetchpages(self, no_order_by: bool = True, as_model: Type[BaseModel] = None) -> Tuple[List[T], int]:
        """
        :param as_model:
        :param no_order_by:
        :return:
        """
        counter = self._select._clone()  # noqa
        counter = counter.offset(None).limit(None)
        if no_order_by:
            counter._order_by = None

        count_stmt = sa.select(sa.func.count(sa.literal_column("*"))).select_from(aliased(counter.subquery()))
        count = await self._session.fetchval(count_stmt)
        data = await self._session.fetch(self._select.statement, as_model=as_model)
        return data, count

    async def fetchdict(self, key: str, value: str = None, as_model: Type[BaseModel] = None) -> dict:
        """
        :param key:
        :param value:
        :param as_model:
        :return:
        """
        return await self._session.fetchdict(self._select.statement, key=key, value=value, as_model=as_model)

    async def fetchval(self):
        """
        :return:
        """
        return await self._session.fetchval(self._select.statement)

    async def fetchrow(self, as_model: Type[BaseModel] = None) -> T:
        return await self._session.fetchrow(self._select.statement, as_model=as_model)

    async def fetchvals(self):
        return await self._session.fetchvals(self._select.statement)

    async def count(self):
        col = sa.func.count(sa.literal_column("*"))
        select = self._select.select_from(col)
        return await self._session.fetchval(select.statement)

    def __str__(self):
        return str(self._select)


class _Delete:
    def __init__(self, delete: Delete, session):
        self._delete = delete  # type:Delete
        self._session = session

    @overload
    def where(self, where_clause):
        """
        :rtype: _Delete
        """
        pass

    @overload
    def where(self, conditional_exp, where_clause):
        """
        :rtype: _Delete
        """
        pass

    def where(self, *clauses):
        where_clause = _format_where(clauses)
        if where_clause is not None:
            self._delete = self._delete.where(where_clause)
        return self

    async def execute(self):
        return await self._session.execute(self._delete)

    def __str__(self):
        return str(self._delete)


def convert_literal_value(value):
    if value is None:
        return 'null'
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, datetime):
        return f"""'{value.isoformat()}'"""
    elif isinstance(value, date):
        return f"""'{value.strftime("%Y-%m-%d")}'"""
    elif isinstance(value, int) or isinstance(value, float):
        return str(value)
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, uuid.UUID):
        return f"""'{value.hex}'"""
    return f"""'{value}'"""


def exec_default(default):
    if default is None:
        return None
    if default.is_sequence:
        raise NotImplementedError()
    elif default.is_callable:
        return default.arg(None)
    return default.arg


def validate(columns: dict, data: dict, is_update: bool = False, is_insert: bool = False):
    """
    :param is_insert:
    :param is_update:
    :param columns:
    :param data:
    :return:
    """
    errors = []

    for name, value in data.items():
        if name not in columns:
            continue
        column = columns[name]
        if value is None or value == "":
            if is_update:
                data[column.name] = exec_default(column.onupdate)
            elif is_insert:
                data[column.name] = exec_default(column.default)
            if not column.default and not column.server_default and not column.nullable:
                errors.append(f"Field '{column.name}' the format is invalid and cannot be empty")
                continue
            continue
        if isinstance(value, Enum):
            value = value.value
        if isinstance(column.type, Integer):
            if not validator.is_int(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be an integer"
                )
            else:
                data[column.name] = Converter.to_int(value)
        elif isinstance(column.type, Numeric) or isinstance(column.type, Float):
            if not validator.is_number(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be a number"
                )
            else:
                data[column.name] = Converter.to_float(value)
        elif isinstance(column.type, Boolean):
            if not validator.is_bool(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be a boolean"
                )
            else:
                data[column.name] = Converter.to_bool(value)
        elif isinstance(column.type, DateTime):
            if not validator.is_datetime(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be a date format yyyy-MM-dd HH:mm:ss"
                )
            else:
                data[column.name] = Converter.to_datetime(value)
        elif isinstance(column.type, Date):
            if not validator.is_date(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be in the date format yyyy-MM-dd"
                )
            else:
                data[column.name] = Converter.to_date(value)
        elif isinstance(column.type, UUID):
            if not validator.is_uuid(value):
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be a UUID"
                )
        elif isinstance(column.type, String):
            s_value = str(value)
            if column.type and column.type.length and len(s_value) > column.type.length:
                errors.append(
                    f"The format of the field '{column.name}' is invalid, "
                    f"the value '{value}' must be less than or equal "
                    f"to {column.type.length} characters"
                )
            data[column.name] = s_value
    if errors:
        raise TypeError(errors)


def condition_clause(conditional_exp: any, criterion):
    ret = conditional_exp
    if callable(conditional_exp):
        ret = conditional_exp()
    if ret is False or ret is None:
        return None
    if isinstance(ret, (list, dict, str)) and not ret:
        return None
    if isinstance(ret, (int, float)) and (not ret and ret != 0):
        return None
    if isinstance(criterion, Callable):
        return criterion()
    return criterion


class ISession:
    def _proxy_id(self) -> int:
        pass


class Session(ISession):
    def __init__(
        self,
        timeout: float = None,
        echo: bool = None,
        loop: asyncio.AbstractEventLoop = None,
        use_poll: bool = None,
        postgres_connection: PostgresConnection = None
    ):
        if use_poll is None:
            self._use_pool = settings.DATABASE_POOL
        else:
            self._use_pool = use_poll
        self._tx: Optional[asyncpg.connection.transaction.Transaction] = None
        self._pool: Optional[asyncpg.pool.Pool] = None
        self._conn: Optional[asyncpg.connection.Connection] = None
        self._timeout = timeout
        if echo is None:
            echo = settings.SQL_ECHO
        self._echo = echo
        self._is_closed = False
        self._loop = loop or asyncio.get_running_loop()
        self._locker = asyncio.Lock()
        self._retry_count = 0
        self._isolation = "read_committed"
        self._postgres_connection: PostgresConnection = postgres_connection or PostgresConnection()

    def set_isolation(self, isolation: str):
        """
        :param isolation: defaults: read_committed
        :return:
        """
        self._isolation = isolation

    async def _ensure_transaction(self, lock: bool = True):
        lock and await self._locker.acquire()
        try:
            if self._tx is None:
                self._tx = self._conn.transaction(isolation=self._isolation)
                await self._tx.start()
        finally:
            lock and self._locker.release()

    async def _ensure_connection(self, lock: bool = True):
        """
        :param lock:
        :return:
        """
        lock and await self._locker.acquire()
        try:
            # logger.debug(f"use poll:{self._use_pool}")
            if self._use_pool:
                if self._pool is None:
                    self._pool = await self._postgres_connection.create_connection(
                        connection_type=ConnectionType.POOL,
                        command_timeout=self._timeout
                    )
                if self._conn is None or self._conn.is_closed():
                    self._conn = await self._pool.acquire(timeout=60)
            else:
                if self._conn is None or self._conn.is_closed():
                    self._conn = await self._postgres_connection.create_connection(
                        connection_type=ConnectionType.DEFAULT,
                        command_timeout=self._timeout,
                        loop=self._loop
                    )
            self._is_closed = False
        except asyncpg.InterfaceError as e:
            self._conn = None
            self._pool = None
            self._retry_count += 1
            if self._retry_count > 1800:
                raise e
            logger.debug(
                f"Reconnect after 1 second after the database connection is disconnected ({e})"
            )
            await asyncio.sleep(1)
            await self._ensure_connection(False)
        except Exception as e:
            lock and self._locker.release()
            raise e
        else:
            lock and self._locker.release()

    def _format_statement(self, statement: Union[str, Any], append_statement: str = None, *params):
        if isinstance(statement, str):
            sql = statement
            raw_sql = sql
            if self._echo and params:
                index = 1
                for p in params:
                    raw_sql = re.sub(
                        fr"\${index}(\D:?)", fr"{convert_literal_value(p)}\g<1>",
                        raw_sql
                    )
                    index += 1
        else:
            result: PGCompiler = statement.compile(dialect=postgresql.dialect(), compile_kwargs={"render_postcompile": True})
            sql = str(result)
            raw_sql = sql
            index = 1
            params = []
            is_update = isinstance(statement, Update)
            is_insert = isinstance(statement, Insert)
            if result.params:
                data = result.params.copy()
                if is_update or is_insert:
                    validate(
                        columns=statement.table.columns,
                        data=data,
                        is_update=is_update,
                        is_insert=is_insert
                    )
                for name, value in data.items():
                    sql = sql.replace(f"%({name})s", f"${index}")
                    if self._echo:
                        raw_sql = raw_sql.replace(f"%({name})s", convert_literal_value(value))
                    params.append(value)
                    index += 1
        if append_statement:
            sql += append_statement
            raw_sql += append_statement
        if self._echo is True:
            logger.debug(str.rjust("", 100, "-"))
            logger.debug("\n" + "\n".join([line.strip() for line in raw_sql.split("\n")]))
            logger.debug(str.rjust("", 100, "-"))
        return sql, params

    async def execute(
        self,
        statement,
        *params,
        append_statement: str = None,
        timeout: float = None
    ):
        try:
            await self._locker.acquire()
            await self._ensure_connection(False)
            await self._ensure_transaction(False)
            sql, params = self._format_statement(statement, append_statement, *params)
            return await self._conn.execute(sql, *params, timeout=timeout)
        except Exception:
            await self.rollback(False)
            raise
        finally:
            self._locker.release()

    def insert(self, table: TableTypes):
        return _Insert(PgInsert(table), self)

    def delete(self, table: TableTypes):
        return _Delete(sa.delete(table), self)

    def update(self, table: TableTypes) -> _Update:
        return _Update(sa.update(table), self)

    def select(self, *columns: Union[sa.Column, TableTypes, Callable], table: TableTypes = None):
        filtered_columns = []
        for column in columns:
            if column is None or column is False:
                continue
            if inspect.isclass(column):
                filtered_columns.append(column)
                continue
            if callable(column):
                _col = column()
                if _col is None or _col is False:
                    continue
                filtered_columns.append(_col)
            else:
                filtered_columns.append(column)
        return _Select(filtered_columns, table, self)

    async def fetch(
        self,
        statement,
        *params,
        timeout: float = None,
        as_model: Type[BaseModel] = None
    ) -> List[T]:
        """
        :param statement:
        :param params:
        :param timeout:
        :param as_model:
        :return:
        """
        return await self._fetch(FetchMethod.FETCH, statement, params, timeout=timeout, as_model=as_model)

    async def fetchgroup(
        self,
        statement,
        *params,
        timeout: float = None,
        groupby: str,
        as_model: Type[BaseModel] = None
    ):
        """

        :param statement:
        :param params:
        :param timeout:
        :param groupby:
        :param as_model:
        :return:
        """
        import itertools
        items = await self.fetch(statement, *params, timeout=timeout, as_model=as_model)
        if as_model:
            return itertools.groupby(items, key=lambda item: getattr(item, groupby))
        return itertools.groupby(items, key=lambda item: item[groupby])

    async def fetchrow(self, statement, *params, timeout: float = None, as_model: Type[BaseModel] = None):
        return await self._fetch(FetchMethod.FETCH_ROW, statement, params, timeout=timeout, as_model=as_model)

    async def fetchval(self, statement: Union[str, Any], *params, timeout: float = None):
        """
        :param statement:
        :param params:
        :param timeout:
        :return:
        """
        return await self._fetch(FetchMethod.FETCH_VAL, statement, params, timeout=timeout)

    async def fetchvals(self, statement, *params, timeout: float = None):
        sql, params = self._format_statement(statement, None, *params)
        await self._ensure_connection()
        rows = await self._conn.fetch(sql, *params, timeout=timeout)
        return [_format_value(item[0]) for item in rows]

    async def fetchdict(
        self,
        statement,
        *params,
        timeout: float = None,
        key: str,
        value: str = None,
        as_model: Type[BaseModel] = None
    ) -> dict:
        Assert.is_not_null(key, "key")
        items = await self.fetch(statement, *params, timeout=timeout, as_model=as_model)
        results = {}
        if not items:
            return results
        for item in items:
            if as_model:
                _key = getattr(item, key)
            else:
                _key = item.get(key, None)
            if value is None:
                results[_key] = item
            else:
                if as_model:
                    _value = getattr(item, value)
                else:
                    _value = item.get(value, None)
                results[_key] = _value
        return results

    async def _fetch(
        self,
        method: FetchMethod,
        statement,
        params,
        append_statement: str = None,
        timeout: float = None,
        as_model: Type[BaseModel] = None
    ) -> Union[List[T], T, dict, str, int]:
        try:
            await self._locker.acquire()
            sql, params = self._format_statement(statement, append_statement, *params)
            await self._ensure_connection(False)
            match method:
                case FetchMethod.FETCH_VAL:
                    value = await self._conn.fetchval(sql, *params, timeout=timeout)
                    return _format_value(value)
                case FetchMethod.FETCH_ROW:
                    value = await self._conn.fetchrow(sql, *params, timeout=timeout)
                    return _format_dict(item=value, as_model=as_model)
                case FetchMethod.FETCH:
                    rows = await self._conn.fetch(sql, *params, timeout=timeout) or []
                    return [_format_dict(item=item, as_model=as_model) for item in rows]
                case _:
                    raise NotImplementedError()
        except Exception:
            await self.rollback(False)
            raise
        finally:
            self._locker.release()

    async def copy_records_to_table(
        self,
        table_name: str, *,
        records,
        columns=None,
        schema_name: str = None,
        timeout: int = None
    ):
        """
        :param table_name:
        :param records:
        :param columns:
        :param schema_name:
        :param timeout:
        :return:
        """
        await self._ensure_connection()
        return await self._conn.copy_records_to_table(
            table_name,
            records=records,
            columns=columns,
            schema_name=schema_name,
            timeout=timeout
        )

    async def commit(self):
        async with self._locker:
            if self._tx is not None:
                if self._tx._state != TransactionState.STARTED:  # noqa
                    return
                await self._tx.commit()
                self._tx = None

    async def rollback(self, lock: bool = True):
        lock and await self._locker.acquire()
        try:
            if self._tx is not None:
                if self._tx._state == TransactionState.STARTED:  # noqa
                    await self._tx.rollback()
                    self._tx = None
        finally:
            lock and self._locker.release()

    async def close(self, lock: bool = True):
        lock and await self._locker.acquire()
        try:
            if self._is_closed:
                return
            await self.rollback(False)
            if self._use_pool:
                self._pool and self._conn and await self._pool.release(self._conn)
            else:
                self._conn and await self._conn.close()
            self._conn = None
            self._is_closed = True
        finally:
            lock and self._locker.release()

    async def safety_close(self):
        # logger.debug(f"TimeOut {self._timeout} automatically close the connection")
        await self.close()

    def safety_close_task(self):
        self._loop.create_task(self.safety_close())

    @property
    def is_closed(self):
        return self._is_closed

    async def __aenter__(self):
        """
        :rtype: Session
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()
        await self.close()

    def __str__(self):
        if self._conn:
            return str(self._conn)
        return None
