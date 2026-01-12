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
uvicorn main:sio_app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 1810

# Production recommendation (multiple workers)
# Note: broadcasting works only with message queue backend!
# pip install python-socketio[redis]
# Then change server creation:

# mgr = socketio.RedisManager("redis://redis:6379/0")
# sio = socketio.AsyncServer(async_mode="asgi", client_manager=mgr, ...)

uvicorn main:sio_app --workers 4 --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 1810
```


## How it works
1. Open terminal, and run ```python main.py```
2. Open another terminal, and run ```python client.py```
3. You will see notifications every 10 seconds.
4. Test Shutdown:
    - Keep the client running.
    - In the terminal running `main.py`, press `Ctrl+C` to send a SIGINT signal.
    - The server will initiate the graceful shutdown process.
    - It will wait for up to 30 minutes for clients to disconnect.
    - If clients are still connected after the timeout, they will be forcefully disconnected.