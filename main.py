import json
import threading
import time
import random
import subprocess
import requests
import os
import tkinter as tk
import keyboard  
from tkinter import messagebox
import socketio
from pynput import keyboard as pynput_keyboard

blocked_words = []  
key_buffer = ''  

def load_blocked_words():
    global blocked_words
    try:
        with open('blocked_words.json', 'r') as f:
            blocked_words_data = json.load(f)
            if isinstance(blocked_words_data, dict) and 'blocked_words' in blocked_words_data:
                blocked_words = blocked_words_data['blocked_words']
            elif isinstance(blocked_words_data, list):
                blocked_words = blocked_words_data
            else:
                print("Unexpected data format in 'blocked_words.json'")
                blocked_words = []
    except Exception as e:
        print(f"Failed to load blocked words: {e}")


sio = socketio.Client()

client_id = os.path.expanduser('~').split('\\')[2]

# Function to create and show the overlay
def show_overlay():
    def check_password():
        if password_entry.get() == "ADMIN":
            root.destroy()
            # Re-enable blocked keys
            keyboard.unblock_key('windows')
            keyboard.unblock_key('ctrl')
            keyboard.unblock_key('alt')
            keyboard.unblock_key('space')
            # Re-enable on the server
            if sio.connected:
                sio.emit('status', {'client_id': client_id, 'status': 'enabled'})
                print("Sent 'enabled' status to server")
        else:
            messagebox.showerror("Incorrect Password", "Incorrect password. Try again.")

    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.attributes('-topmost', True) 

    # Disable closing the window using the close button
    root.protocol("WM_DELETE_WINDOW", lambda: None)

    # Block specific keys
    keyboard.block_key('windows')
    keyboard.block_key('ctrl')
    keyboard.block_key('alt')
    keyboard.block_key('space')

    label = tk.Label(root, text="System Disabled", font=("Helvetica", 48))
    label.pack(pady=50)

    password_label = tk.Label(root, text="Enter Password:", font=("Helvetica", 24))
    password_label.pack(pady=20)

    password_entry = tk.Entry(root, show="*", font=("Helvetica", 24))
    password_entry.pack()

    submit_button = tk.Button(root, text="Submit", command=check_password, font=("Helvetica", 24))
    submit_button.pack(pady=20)

    root.mainloop()

@sio.event
def connect():
    print('Connected to server')
    sio.emit('status', {'client_id': client_id, 'status': 'enabled'})

@sio.event
def disconnect():
    print('Disconnected from server')

def send_disabled_status(blocked_word):
    if sio.connected:
        sio.emit('blocked_word', {'client_id': client_id, 'word': blocked_word})
        sio.emit('status', {'client_id': client_id, 'status': 'disabled'})
        print(f"Sent 'disabled' status and blocked word '{blocked_word}' to server")
        show_overlay()

def fetch_blocked_words_from_server():
    """Fetch the blocked words from the server and update the local file."""
    try:
        # Replace this URL with your server's actual address
        server_url = 'http://<server_ip>:5000/request_blocked_words'
        
        # Send GET request to fetch blocked words
        response = requests.get(server_url)
        
        # Check if the request was successful
        if response.status_code == 200:
            blocked_words_from_server = response.json().get('blocked_words', [])
            # Update the blocked words locally
            global blocked_words
            blocked_words = blocked_words_from_server
            # Save the blocked words to local blocked_words.json
            with open('blocked_words.json', 'w') as f:
                json.dump(blocked_words, f, indent=4)
            print("Blocked words updated successfully.")
        else:
            print(f"Failed to fetch blocked words: {response.status_code}")
    except Exception as e:
        print(f"An error occurred while fetching blocked words: {e}")

def on_press(key):
    global key_buffer
    try:
        if hasattr(key, 'char') and key.char:  
            key_buffer += key.char
        elif key == pynput_keyboard.Key.space:
            key_buffer += ' '
        elif key == pynput_keyboard.Key.backspace and len(key_buffer) > 0:
            key_buffer = key_buffer[:-1]

        for word in blocked_words:
            if word.lower() in key_buffer.lower():
                send_disabled_status(word)
                key_buffer = ''  
                break
    except Exception as e:
        print(f"Error in on_press: {e}")

def run_functions_every_5_seconds(funcs):
    """
    Runs the provided list of functions every 5 seconds.
    :param funcs: A list of functions to run.
    """
    def execute_functions():
        while True:
            for func in funcs:
                func()  
            time.sleep(5)  
    
    threading.Thread(target=execute_functions, daemon=True).start()

try:
    sio.connect('http://<server_ip>:5000') 
    run_functions_every_5_seconds([fetch_blocked_words_from_server, load_blocked_words])
except Exception as e:
    print(f"Failed to connect to server: {e}")

with pynput_keyboard.Listener(on_press=on_press) as listener:
    listener.join()

while True:
    time.sleep(1)


