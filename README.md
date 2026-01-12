## Graceful Shutdown Logic (python-socketio version)

- Uses FastAPI `lifespan` context manager
- Tracks active SIDs in `active_clients` dict
- On SIGTERM/SIGINT → sets shutdown flag + timer
- Waits up to 30 minutes while checking `len(active_clients)`
- Each worker manages its own clients independently
- After timeout → force disconnects remaining clients

Broadcasting to all clients only works correctly with a message queue backend when using multiple workers.

```bash
# Development (single worker + reload)
uvicorn main:sio_app --host 0.0.0.0 --port 8000 --reload

# Production recommendation (multiple workers)
# Note: broadcasting works only with message queue backend!
# pip install python-socketio[redis]
# Then change server creation:

# mgr = socketio.RedisManager("redis://redis:6379/0")
# sio = socketio.AsyncServer(async_mode="asgi", client_manager=mgr, ...)

uvicorn main:sio_app --workers 4 --host 0.0.0.0 --port 8000
```