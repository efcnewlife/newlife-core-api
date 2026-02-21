import asyncio
import datetime
import hashlib
import inspect
import json
import uuid
from typing import Union, Callable, Type, Any, Optional
from unittest.mock import MagicMock, AsyncMock

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql.dml import Insert as PgInsert

from portal.libs.database import Session
from portal.libs.database.aio_orm import _Select, _Update, _Delete, _Insert, TableTypes


def md5_encrypt(text: str, salt: str = ''):
    return hashlib.md5((salt + text).encode()).hexdigest()


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        else:
            return json.JSONEncoder.default(self, obj)


class SessionMockError(Exception):
    pass


class SelectMock(_Select):
    def mock(self, return_value: Any = None) -> MagicMock:
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetch(self, return_value: Any = None) -> MagicMock:
        """Mock the fetch method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchgroup(self, groupby: str, return_value: Any = None) -> MagicMock:
        """Mock the fetchgroup method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchpages(self, return_value: Any = None) -> MagicMock:
        """Mock the fetchpages method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchdict(self, key: str, value: str = None, return_value: Any = None) -> MagicMock:
        """Mock the fetchdict method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchval(self, return_value: Any = None) -> MagicMock:
        """Mock the fetchval method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchrow(self, return_value: Any = None) -> MagicMock:
        """Mock the fetchrow method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_fetchvals(self, return_value: Any = None) -> MagicMock:
        """Mock the fetchvals method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock

    def mock_count(self, return_value: Any = None) -> MagicMock:
        """Mock the count method"""
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._select.statement, mock)
        return mock


class UpdateMock(_Update):
    def mock(self, return_value: Any = None, name: str = None) -> MagicMock:
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._update, mock, name=name)
        return mock


class DeleteMock(_Delete):
    def mock(self, return_value: Any = None, name: str = None) -> MagicMock:
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._delete, mock, name=name)
        return mock


class InsertMock(_Insert):
    def mock(self, return_value: Any = None, name: str = None) -> MagicMock:
        mock = MagicMock(return_value=return_value)
        # noinspection PyUnresolvedReferences
        self._session.set_mock(self._insert, mock, name=name)
        return mock


class SessionMock(Session):
    def __init__(
        self,
        timeout: float = None,
        echo: bool = None,
        loop: asyncio.AbstractEventLoop = None,
        use_poll: bool = None,
        raise_on_unmatch: bool = False
    ):
        super().__init__(timeout, echo, loop, use_poll)
        self._statement_mocks: dict[str, MagicMock] = {}
        self._raise_on_unmatch = raise_on_unmatch

    def set_mock(self, statement: Any, mock: MagicMock, params: tuple = None, name: str = None):
        key, _ = self._to_key(statement, params)
        self._statement_mocks[key] = mock

    def _to_key(self, statement: Any, params: tuple = None):
        output_params = None
        if isinstance(statement, str):
            strs = [statement]
        else:
            compiled_statement = statement.compile(dialect=postgresql.dialect())
            strs = [str(compiled_statement)]
            if compiled_statement.params:
                strs.append(json.dumps(compiled_statement.params, cls=DateEncoder))
                output_params = compiled_statement.params
        if params:
            strs.append(json.dumps(list(params)))
        return md5_encrypt(''.join(strs)), output_params

    async def _ensure_connection(self, lock: bool = True):
        # self._ensure_conn()
        pass

    async def _ensure_transaction(self, lock: bool = True):
        pass

    def select(self, *columns: Union[sa.Column, TableTypes, Callable], table: Type[sa.Table] = None) -> SelectMock:
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
        return SelectMock(filtered_columns, table, session=self)

    def insert(self, table: Type[sa.Table]) -> InsertMock:
        return InsertMock(PgInsert(table), self)

    def delete(self, table: Type[sa.Table]) -> DeleteMock:
        return DeleteMock(sa.delete(table), self)

    def update(self, table: Type[sa.Table]) -> UpdateMock:
        return UpdateMock(sa.update(table), self)

    async def commit(self):
        print('commit')

    async def rollback(self, lock: bool = True):
        print('rollback')

    async def close(self, lock: bool = True):
        pass

    async def safety_close(self):
        print('safety_close')

    def mock_fetch(self, statement: Any, *params, return_value: Any = None) -> Any:
        mock = MagicMock(return_value=return_value)
        self.set_mock(statement, mock, params)
        return mock

    def mock_fetchval(self, statement: Any, *params, return_value: Any = None):
        return self.mock_fetch(statement, params, return_value)

    def mock_fetchrow(self, statement: Any, *params, return_value: Any = None):
        return self.mock_fetch(statement, params, return_value)

    def mock_fetchpages(self, statement: Any, *params, return_value: Any = None):
        return self.mock_fetch(statement, params, return_value)

    def mock_execute(self, statement: Any, *params, return_value: Any = None):
        return self.mock_fetch(statement, params, return_value)

    async def fetch(self, statement, *params, timeout: float = None, as_model: Type[BaseModel] = None) -> Any:
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchgroup(self, statement, *params, timeout: float = None, groupby: str = None, as_model: Type[BaseModel] = None):
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchpages(self, statement, *params, timeout: float = None, as_model: Type[BaseModel] = None):
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchdict(self, statement, *params, timeout: float = None, key: str = None, value: str = None, as_model: Type[BaseModel] = None):
        key_, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key_, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchval(self, statement: Union[str, Any], *params, timeout: float = None):
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchrow(self, statement, *params, timeout: float = None, as_model: Type[BaseModel] = None):
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def fetchvals(self, statement, *params, timeout: float = None):
        key, output_params = self._to_key(statement, params)
        mock: Optional[MagicMock] = self._statement_mocks.get(key, None)
        if not mock:
            if self._raise_on_unmatch:
                raise SessionMockError(f'没有符合条件的 Mock 函数 ({statement})')
            print()
            print(f'没有匹配符合条件的 Mock 函数, SQL: {statement} ; PARAMS: {params or output_params} ;')
            return MagicMock(return_value=None)()
        return mock()

    async def execute(self, statement, *params, append_statement: str = None, timeout: float = None):
        return await self.fetch(statement, *params, timeout=timeout, as_model=None)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        return self
