import asyncio
import time
from pathlib import Path

import pytest
from starlette.responses import FileResponse

import main


@pytest.mark.asyncio
async def test_connect_disconnect_message_and_emits(monkeypatch):
    # capture emits
    emits = []

    async def fake_emit(event, data=None, *args, **kwargs):
        emits.append((event, data))

    monkeypatch.setattr(main, "sio", main.sio)  # ensure attribute exists
    monkeypatch.setattr(main.sio, "emit", fake_emit)

    # reset state
    main.active_clients.clear()
    main.shutdown_requested = False

    # connect
    await main.connect("sid-test", {})
    assert "sid-test" in main.active_clients
    assert emits and emits[-1][0] == "welcome"

    # message echo
    await main.message("sid-test", {"x": 1})
    assert emits and emits[-1][0] == "message"
    assert emits[-1][1]["from"] == "sid-test"
    assert emits[-1][1]["data"] == {"x": 1}

    # disconnect
    await main.disconnect("sid-test")
    assert "sid-test" not in main.active_clients


@pytest.mark.asyncio
async def test_broadcaster_emits_once_then_stops(monkeypatch):
    emits = []

    async def fake_emit(event, data=None, *args, **kwargs):
        emits.append((event, data))

    # set one active client so broadcaster will emit
    main.active_clients.clear()
    main.active_clients["s1"] = time.monotonic()
    main.shutdown_requested = False

    monkeypatch.setattr(main.sio, "emit", fake_emit)

    # make sleep set shutdown after first sleep call so loop terminates
    async def fake_sleep(seconds):
        # set shutdown so broadcaster exits after the first iteration
        main.shutdown_requested = True
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await main.broadcaster()

    assert any(ev == "notification" for ev, _ in emits)

    # cleanup
    main.active_clients.clear()
    main.shutdown_requested = False


@pytest.mark.asyncio
async def test_lifespan_creates_and_cancels_task(monkeypatch):
    # Dummy awaitable task returned by patched create_task
    class DummyTask:
        def __init__(self):
            self.cancelled = False
            self.awaited = False

        def cancel(self):
            self.cancelled = True

        def __await__(self):
            async def _coro():
                self.awaited = True
                return None
            return _coro().__await__()

    dummy = DummyTask()

    # patch broadcaster to a no-op coroutine to avoid side effects
    async def dummy_broadcaster():
        await asyncio.sleep(0)

    monkeypatch.setattr(main, "broadcaster", dummy_broadcaster)

    # patch create_task to return our dummy
    monkeypatch.setattr(asyncio, "create_task", lambda coro: dummy)

    # ensure no active clients so shutdown loop doesn't wait
    main.active_clients.clear()
    main.shutdown_requested = False

    # enter/exit lifespan
    async with main.lifespan(main.app):
        # inside startup
        assert not dummy.cancelled
        assert not dummy.awaited

    # after exit the dummy task should have been cancelled and awaited
    assert dummy.cancelled is True
    assert dummy.awaited is True

    # restore flag
    main.shutdown_requested = False


@pytest.mark.asyncio
async def test_home_page_returns_fileresponse(tmp_path):
    resp = await main.home_page()
    assert isinstance(resp, FileResponse)
    assert getattr(resp, "media_type", None) == "text/html"
    assert getattr(resp, "status_code", None) == 200

