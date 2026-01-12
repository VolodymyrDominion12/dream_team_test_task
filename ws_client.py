import socketio
import time

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server!")

@sio.event
def notification(data):
    print(f"Received notification: {data}")

@sio.event
def disconnect():
    print("Disconnected from server.")

# Connect to the specific path defined in main.py
sio.connect('http://localhost:8000', socketio_path='/socket.io')
sio.wait()