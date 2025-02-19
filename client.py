import time
import random
import subprocess
import sys

# Try to install socketio if it's not found
try:
    import socketio
except ModuleNotFoundError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'socketio'])
    import socketio

sio = socketio.Client()

@sio.event
def connect():
    print('Connected to server')

@sio.event
def disconnect():
    print('Disconnected from server')
