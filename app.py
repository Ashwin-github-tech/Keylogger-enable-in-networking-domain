import os
import sqlite3
import json
from flask import Flask, jsonify, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ----------------------------------
# Flask & SocketIO Setup
# ----------------------------------

app = Flask(_name_)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------------------------
# SQLite Setup for Client Statuses
# ----------------------------------
DB_NAME = 'clients.db'

def init_db():
    """Create clients table if it doesn't exist (with columns for ip, etc.)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT UNIQUE,
                    status TEXT,
                    sid TEXT,
                    ip TEXT
                )''')
    conn.commit()
    create_users_table(conn)
    create_history_table(conn)
    conn.close()

def create_users_table(conn):
    """Create users table if it doesn't exist."""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )''')
    conn.commit()

def create_history_table(conn):
    """Create history table if it doesn't exist."""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT (DATETIME('now', '+05:30')),
                    word TEXT NOT NULL,
                    FOREIGN KEY (client_id) REFERENCES clients(client_id)
                )''')
    conn.commit()


def set_client_status(client_id, status, sid, ip):
    """Insert or update a client status record by client_id."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Insert or replace to update existing client_id row
    c.execute('''INSERT OR REPLACE INTO clients (client_id, status, sid, ip)
                 VALUES (?, ?, ?, ?)''', (client_id, status, sid, ip))
    conn.commit()
    conn.close()

def add_history_record(client_id, word):
    """Add a record to the history table."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO history (client_id, word) VALUES (?, ?)", (client_id, word))
    conn.commit()
    conn.close()

def remove_client_by_sid(sid):
    """Remove a client record by its SocketIO session ID."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM clients WHERE sid = ?", (sid,))
    conn.commit()
    conn.close()

def get_all_statuses():
    """Return a dict: {client_id: {"status": ..., "ip": ...}, ...}"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT client_id, status, ip FROM clients")
    rows = c.fetchall()
    conn.close()
    return {row[0]: {'status': row[1], 'ip': row[2]} for row in rows}

# Initialize the DB at startup
init_db()

# ----------------------------------
# File with Blocked Words
# ----------------------------------
BLOCKED_WORDS_FILE = os.path.join(os.path.dirname(_file_), 'blocked_words.json')

def read_blocked_words():
    """Load the blocked words from JSON and return as a list."""
    with open(BLOCKED_WORDS_FILE, 'r') as f:
        data = json.load(f)
    return data.get("blocked_words", [])

def write_blocked_words(words_list):
    """Write the given list of words to the JSON file."""
    with open(BLOCKED_WORDS_FILE, 'w') as f:
        json.dump({"blocked_words": words_list}, f, indent=2)

# ----------------------------------
# Routes
# ----------------------------------
@app.route('/')
@login_required
def index():
    """
    Main dashboard showing connected clients and their statuses.
    """
    current_statuses = get_all_statuses()
    return render_template('index.html', statuses=current_statuses)

@app.route('/update_status', methods=['POST'])
def update_status():
    """
    Example endpoint for your "Enable"/"Disable" buttons in index.html.
    Currently, it doesn't directly update the DB. In a real setup,
    you'd either broadcast to clients or do something else.
    """
    # Read incoming JSON
    data = request.get_json()
    new_status = data.get("status", "enabled")
    return {"message": f"Set status to {new_status}"}, 200

# ----------------------------------
# SocketIO Events
# ----------------------------------
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    remove_client_by_sid(request.sid)
    emit('status_update', get_all_statuses(), broadcast=True)

@socketio.on('status')
def handle_status(data):
    """
    Receives {client_id, status} from a connected client.
    Updates DB and broadcasts new status to all.
    """
    client_id = data['client_id']
    status = data['status']
    client_ip = request.remote_addr  # The IP address of the client connection
    set_client_status(client_id, status, request.sid, client_ip)
    emit('status_update', get_all_statuses(), broadcast=True)

@socketio.on('blocked_word')
def handle_blocked_word(data):
    """
    Receives {client_id, word} when a blocked word is detected.
    Adds the record to the history table.
    """
    client_id = data['client_id']
    word = data['word']
    add_history_record(client_id, word)
    print(f"Blocked word '{word}' detected from client '{client_id}' and recorded.")

# ----------------------------------
# Authentication Routes
# ----------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            session['user_id'] = username
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username already exists')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

# ----------------------------------
# Logout Route
# ----------------------------------
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# ----------------------------------
# Manage Blocked Words Route
# ----------------------------------
@app.route('/history')
@login_required
def history():
    """View the history of blocked words."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT timestamp, client_id, word FROM history ORDER BY timestamp DESC")
    history_records = c.fetchall()
    conn.close()
    return render_template('history.html', history_records=history_records)

@app.route('/manage_blocked_words', methods=['GET', 'POST'])
@login_required
def manage_blocked_words():
    if request.method == 'POST':
        action = request.form.get('action')
        words_list = read_blocked_words()

        if action == 'add':
            new_word = request.form.get('new_word', '').strip()
            if new_word and new_word.lower() not in [w.lower() for w in words_list]:
                words_list.append(new_word)
                write_blocked_words(words_list)

        elif action == 'delete':
            word_to_delete = request.form.get('word_to_delete', '')
            words_list = [w for w in words_list if w != word_to_delete]
            write_blocked_words(words_list)

        elif action == 'edit':
            old_word = request.form.get('old_word', '')
            new_word = request.form.get('new_word', '').strip()
            if old_word in words_list and new_word:
                updated_list = []
                for w in words_list:
                    if w == old_word:
                        updated_list.append(new_word)
                    else:
                        updated_list.append(w)
                write_blocked_words(updated_list)

        return redirect(url_for('manage_blocked_words'))

    # GET request
    current_words = read_blocked_words()
    return render_template('manage_blocked_words.html', blocked_words=current_words)


@app.route('/request_blocked_words', methods=['GET', 'POST'])

def send_blocked_words():
    """Send the current blocked words list to the requesting client."""
    blocked_words = read_blocked_words()
    return jsonify({'blocked_words': blocked_words})


# ----------------------------------
# Entry Point
# ----------------------------------
if _name_ == '_main_':
    socketio.run(app, host='<server_ip>', port=5000, debug=True)