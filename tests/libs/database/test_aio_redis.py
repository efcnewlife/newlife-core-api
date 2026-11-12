"""
Redis client configuration targets a single database 0 keyspace (Azure Managed Redis supports db 0 only).
"""

import ssl

from redis.asyncio.connection import Connection, SSLConnection
from redis.exceptions import ConnectionError, TimeoutError

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
