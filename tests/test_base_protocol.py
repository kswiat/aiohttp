import asyncio
from contextlib import suppress
from unittest import mock

import pytest

from aiohttp.base_protocol import BaseProtocol


def test_loop(loop) -> None:
    asyncio.set_event_loop(None)
    pr = BaseProtocol(loop=loop)
    assert pr._loop is loop


def test_default_loop(loop) -> None:
    asyncio.set_event_loop(loop)
    pr = BaseProtocol()
    assert pr._loop is loop


def test_pause_writing(loop) -> None:
    pr = BaseProtocol(loop=loop)
    assert not pr._paused
    pr.pause_writing()
    assert pr._paused


def test_resume_writing_no_waiters(loop) -> None:
    pr = BaseProtocol(loop=loop)
    pr.pause_writing()
    assert pr._paused
    pr.resume_writing()
    assert not pr._paused


def test_connection_made(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    assert pr.transport is None
    pr.connection_made(tr)
    assert pr.transport is not None


def test_connection_lost_not_paused(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    assert not pr._connection_lost
    pr.connection_lost(None)
    assert pr.transport is None
    assert pr._connection_lost


def test_connection_lost_paused_without_waiter(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    assert not pr._connection_lost
    pr.pause_writing()
    pr.connection_lost(None)
    assert pr.transport is None
    assert pr._connection_lost


async def test_drain_lost(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.connection_lost(None)
    with pytest.raises(ConnectionResetError):
        await pr._drain_helper()


async def test_drain_not_paused(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    assert pr._drain_waiter is None
    await pr._drain_helper()
    assert pr._drain_waiter is None


async def test_resume_drain_waited(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.pause_writing()

    t = loop.create_task(pr._drain_helper())
    await asyncio.sleep(0)

    assert pr._drain_waiter is not None
    pr.resume_writing()
    assert (await t) is None
    assert pr._drain_waiter is None


async def test_lost_drain_waited_ok(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.pause_writing()

    t = loop.create_task(pr._drain_helper())
    await asyncio.sleep(0)

    assert pr._drain_waiter is not None
    pr.connection_lost(None)
    assert (await t) is None
    assert pr._drain_waiter is None


async def test_lost_drain_waited_exception(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.pause_writing()

    t = loop.create_task(pr._drain_helper())
    await asyncio.sleep(0)

    assert pr._drain_waiter is not None
    exc = RuntimeError()
    pr.connection_lost(exc)
    with pytest.raises(RuntimeError) as cm:
        await t
    assert cm.value is exc
    assert pr._drain_waiter is None


async def test_lost_drain_cancelled(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.pause_writing()

    fut = loop.create_future()

    async def wait():
        fut.set_result(None)
        await pr._drain_helper()

    t = loop.create_task(wait())
    await fut
    t.cancel()

    assert pr._drain_waiter is not None
    pr.connection_lost(None)
    with suppress(asyncio.CancelledError):
        await t
    assert pr._drain_waiter is None


async def test_resume_drain_cancelled(loop) -> None:
    pr = BaseProtocol(loop=loop)
    tr = mock.Mock()
    pr.connection_made(tr)
    pr.pause_writing()

    fut = loop.create_future()

    async def wait():
        fut.set_result(None)
        await pr._drain_helper()

    t = loop.create_task(wait())
    await fut
    t.cancel()

    assert pr._drain_waiter is not None
    pr.resume_writing()
    with suppress(asyncio.CancelledError):
        await t
    assert pr._drain_waiter is None
