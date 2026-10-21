"""
Session after-commit callbacks run only once a transaction actually commits.
"""

import asyncio

import pytest
from asyncpg.transaction import TransactionState

from portal.libs.database.aio_orm import Session


class _FakeTransaction:
    def __init__(self, state: TransactionState = TransactionState.STARTED):
        self._state = state
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True
        self._state = TransactionState.COMMITTED

    async def rollback(self):
        self.rolled_back = True
        self._state = TransactionState.ROLLEDBACK


def _session(tx: _FakeTransaction) -> Session:
    session = Session.__new__(Session)
    session._tx = tx
    session._locker = asyncio.Lock()
    session._after_commit_callbacks = []
    return session


@pytest.mark.asyncio
async def test_callbacks_run_after_commit():
    tx = _FakeTransaction()
    session = _session(tx)
    seen: list[bool] = []

    async def callback():
        seen.append(tx.committed)

    session.add_after_commit(callback)
    await session.commit()

    assert seen == [True]
    await session.commit()
    assert seen == [True]


@pytest.mark.asyncio
async def test_rollback_discards_callbacks():
    session = _session(_FakeTransaction())
    seen: list[str] = []

    async def callback():
        seen.append("sent")

    session.add_after_commit(callback)
    await session.rollback()
    await session.commit()

    assert seen == []


@pytest.mark.asyncio
async def test_failed_transaction_commit_discards_callbacks():
    session = _session(_FakeTransaction(TransactionState.FAILED))
    seen: list[str] = []

    async def callback():
        seen.append("sent")

    session.add_after_commit(callback)
    await session.commit()

    assert seen == []


@pytest.mark.asyncio
async def test_callback_failure_does_not_block_others():
    session = _session(_FakeTransaction())
    seen: list[str] = []

    async def broken():
        raise RuntimeError("mail down")

    async def ok():
        seen.append("sent")

    session.add_after_commit(broken)
    session.add_after_commit(ok)
    await session.commit()

    assert seen == ["sent"]
