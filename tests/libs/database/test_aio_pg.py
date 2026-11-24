"""
PostgreSQL pool size and acquire timeout. An asyncpg pool with min_size=0 opens no connection, so no database is needed.
"""

import asyncio

import pytest

from portal.config import settings
from portal.libs.database import PostgresConnection, Session, aio_orm
from portal.libs.database.aio_pg import ConnectionType, PoolAcquireTimeoutError


@pytest.mark.asyncio
async def test_pool_max_size_comes_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_POOL_MAX_SIZE", 7)

    pool = await PostgresConnection().create_connection(ConnectionType.POOL)

    assert pool.get_max_size() == 7
    await pool.close()


class _BusyPool:
    """Every connection is in use; honors the acquire timeout like asyncpg does."""

    async def acquire(self, *, timeout=None):
        await asyncio.wait_for(asyncio.Event().wait(), timeout)


class _BusyPostgresConnection:
    async def create_connection(self, *_args, **_kwargs):
        return _BusyPool()


class _RecordingPool:
    def __init__(self):
        self.timeouts: list[float] = []

    async def acquire(self, *, timeout=None):
        self.timeouts.append(timeout)
        raise TimeoutError


@pytest.mark.asyncio
async def test_acquire_waits_at_most_five_seconds(mocker):
    pool = _RecordingPool()
    session = Session(postgres_connection=mocker.Mock(create_connection=mocker.AsyncMock(return_value=pool)))

    with pytest.raises(PoolAcquireTimeoutError):
        await session.fetchval("SELECT 1")

    assert pool.timeouts == [5]


@pytest.mark.asyncio
async def test_a_busy_pool_raises_pool_acquire_timeout_and_leaves_the_session_closable(monkeypatch):
    monkeypatch.setattr(aio_orm, "POOL_ACQUIRE_TIMEOUT_SECONDS", 0.01)
    session = Session(postgres_connection=_BusyPostgresConnection())

    for run in (session.fetchval, session.fetchvals, session.execute):
        with pytest.raises(PoolAcquireTimeoutError):
            await run("SELECT 1")

    await session.close()
