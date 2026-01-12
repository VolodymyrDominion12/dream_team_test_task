import asyncio
import os
from contextlib import asynccontextmanager, suppress
import time
from pathlib import Path

from fastapi import FastAPI
from loguru import logger
import socketio
from fastapi.responses import FileResponse


sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    ping_timeout=60,
    ping_interval=25
)

# Track active clients (sid → last seen, or just count)
active_clients: dict[str, float] = {}   # sid: last_activity_timestamp

shutdown_requested = False
shutdown_start_time = None
MAX_GRACE_PERIOD = 30 * 60  # 30 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup")
    # start background broadcaster
    bg_task = asyncio.create_task(broadcaster())

    pid = os.getpid()
    logger.info(f"Process ID: {pid}")

    global shutdown_requested, shutdown_start_time, active_clients

    try:
        yield
    finally:
        # signal shutdown and clean up the background task
        logger.warning("Shutdown signal received → starting graceful shutdown...")

        shutdown_requested = True
        shutdown_start_time = time.monotonic()

        # wait for clients (existing logic can remain)...
        remaining = MAX_GRACE_PERIOD
        logger.info(f"{len(active_clients)} active client(s) connected. ")
        logger.info(f"{remaining} seconds grace period for clients to disconnect.")
        while len(active_clients) > 0 and remaining > 0:
            logger.info(
                f"Waiting for clients to disconnect... "
                f"Active: {len(active_clients)} | "
                f"Time left: {int(remaining)//60:02d}m {int(remaining)%60:02d}s"
            )
            await asyncio.sleep(5)
            remaining = max(0, MAX_GRACE_PERIOD - (time.monotonic() - shutdown_start_time))

        if len(active_clients) > 0:
            logger.error(f"Force shutdown after timeout! {len(active_clients)} client(s) still connected!")
            for sid in list(active_clients):
                await sio.disconnect(sid, ignore_queue=True)
        else:
            logger.success("All clients disconnected gracefully ✓")

        # cancel/await the broadcaster
        bg_task.cancel()
        with suppress(asyncio.CancelledError):
            await bg_task


app = FastAPI(lifespan=lifespan)
sio_app = socketio.ASGIApp(sio, app)


# ───────────────────────────────────────────────
# Socket.IO Events
# ───────────────────────────────────────────────
@sio.event
async def connect(sid, environ):
    global active_clients
    active_clients[sid] = time.monotonic()
    logger.info(f"Client connected  {sid} | Active: {len(active_clients)}")
    await sio.emit("welcome", {"msg": "Welcome! Real-time notifications started"})


@sio.event
async def disconnect(sid):
    global active_clients
    if sid in active_clients:
        del active_clients[sid]
    logger.info(f"Client disconnected {sid} | Active: {len(active_clients)}")


# Optional: client can send messages (for example chat-like)
@sio.event
async def message(sid, data):
    logger.info(f"Message from {sid}: {data}")
    await sio.emit("message", {"from": sid, "data": data})


# ───────────────────────────────────────────────
# Background broadcaster task (demo notifications)
# ───────────────────────────────────────────────
async def broadcaster():
    global shutdown_requested, active_clients
    counter = 0
    while True:
        if shutdown_requested:
            logger.info("Broadcaster stopped due to shutdown")
            return

        if active_clients:
            counter += 1
            await sio.emit(
                "notification",
                {"id": counter, "text": f"Server notification #{counter}", "time": time.time()}
            )
            logger.debug(f"Broadcast sent #{counter} to {len(active_clients)} clients")

        await asyncio.sleep(10)





@app.get("/")
async def home_page():
    html_path = Path(__file__).parent / "html_client.html"
    return FileResponse(html_path, media_type="text/html")


# Important: mount the socket.io ASGI app
app.mount("/", sio_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app_asgi",
        host="0.0.0.0",
        port=8000,
        reload=False,
        timeout_graceful_shutdown=MAX_GRACE_PERIOD + 10  # Give uvicorn slightly more time than our logic
    )

