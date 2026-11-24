"""
Redis client configuration targets a single database 0 keyspace (Azure Managed Redis supports db 0 only).
"""

import asyncio
import ssl
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import BlockingConnectionPool
from redis.asyncio.connection import Connection, SSLConnection
from redis.exceptions import ConnectionError, MaxConnectionsError, TimeoutError

from portal.libs.database import aio_redis
from portal.libs.database.aio_redis import RedisPool, create_redis_client


def _connection(url: str):
    return create_redis_client(url).connection_pool.make_connection()


def test_rediss_url_verifies_server_certificate_and_hostname():
    conn = _connection("rediss://:secret@example.redis.azure.net:10000")

    assert isinstance(conn, SSLConnection)
    assert conn.check_hostname is True
    assert conn.cert_reqs == ssl.CERT_REQUIRED
    assert conn.port == 10000


def test_plain_url_without_path_uses_database_zero():
    conn = _connection("redis://localhost:6379")

    assert type(conn) is Connection
    assert conn.db == 0


def test_client_retries_connection_errors_and_checks_idle_connections():
    conn = _connection("rediss://:secret@example.redis.azure.net:10000")

    assert conn.retry.get_retries() >= 3
    assert ConnectionError in conn.retry._supported_errors
    assert TimeoutError in conn.retry._supported_errors
    assert conn.health_check_interval > 0
    assert conn.socket_keepalive is True


def test_client_decodes_responses():
    client = create_redis_client("redis://localhost:6379")

    assert client.connection_pool.connection_kwargs["decode_responses"] is True


def test_pool_returns_one_shared_client(monkeypatch):
    monkeypatch.setattr("portal.libs.database.aio_redis.settings.REDIS_URL", "redis://localhost:6379")
    pool = RedisPool()

    assert pool.create() is pool.create()


def _exhaust(pool) -> None:
    """Take every connection without opening one."""
    for _ in range(pool.max_connections):
        pool.get_available_connection()


def test_client_waits_at_most_five_seconds_for_one_of_100_connections():
    pool = create_redis_client("redis://localhost:6379").connection_pool

    assert isinstance(pool, BlockingConnectionPool)
    assert (pool.timeout, pool.max_connections) == (5, 100)


@pytest.mark.asyncio
async def test_exhausted_pool_raises_max_connections_error_after_the_timeout(monkeypatch):
    monkeypatch.setattr(aio_redis, "POOL_TIMEOUT_SECONDS", 0.01)
    client = create_redis_client("redis://redis.invalid:6379")
    _exhaust(client.connection_pool)

    with pytest.raises(MaxConnectionsError):
        await client.get("key")


@pytest.mark.asyncio
async def test_waiting_command_gets_a_released_connection(monkeypatch):
    monkeypatch.setattr(aio_redis, "POOL_TIMEOUT_SECONDS", 5)
    pool = create_redis_client("redis://localhost:6379").connection_pool
    _exhaust(pool)
    released = next(iter(pool._in_use_connections))
    monkeypatch.setattr(released, "connect", AsyncMock())
    monkeypatch.setattr(released, "can_read", AsyncMock(return_value=False))

    waiting = asyncio.create_task(pool.get_connection())
    await asyncio.sleep(0)
    await pool.release(released)

    assert await waiting is released


@pytest.mark.asyncio
async def test_unreachable_redis_is_not_reported_as_an_exhausted_pool(monkeypatch):
    pool = create_redis_client("redis://localhost:6379").connection_pool
    monkeypatch.setattr(pool, "ensure_connection", AsyncMock(side_effect=ConnectionError("connection refused")))

    with pytest.raises(ConnectionError) as raised:
        await pool.get_connection()

    assert not isinstance(raised.value, MaxConnectionsError)
