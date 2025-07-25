from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from datetime import datetime
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'konnichiyabs-secret-key'
socketio = SocketIO(app)

# Simple in-memory user tracking
connected_users = set()

def get_db_connection():
    conn = sqlite3.connect('chat.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            msg TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            friend_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(friend_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            error = "Username and password required."
        else:
            conn = get_db_connection()
            try:
                conn.execute(
                    'INSERT INTO users (username, password) VALUES (?, ?)',
                    (username, generate_password_hash(password))
                )
                conn.commit()
                session['username'] = username
                return redirect(url_for('friends'))
            except sqlite3.IntegrityError:
                error = "Username already exists."
            finally:
                conn.close()
    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('friends'))
        else:
            error = "Invalid username or password."
    return render_template('login.html', error=error)

@app.route('/friends', methods=['GET', 'POST'])
def friends():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    user_id = user['id']

    error = None
    # Add friend logic
    if request.method == 'POST':
        friend_username = request.form.get('friend_username')
        if friend_username and friend_username != username:
            friend = conn.execute('SELECT id FROM users WHERE username = ?', (friend_username,)).fetchone()
            if not friend:
                error = "User does not exist."
            else:
                friend_id = friend['id']
                # Check if already friends
                already = conn.execute(
                    'SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id)
                ).fetchone()
                if already:
                    error = "Already friends."
                else:
                    # Add mutual friendship
                    conn.execute('INSERT INTO friends (user_id, friend_id) VALUES (?, ?)', (user_id, friend_id))
                    conn.execute('INSERT INTO friends (user_id, friend_id) VALUES (?, ?)', (friend_id, user_id))
                    conn.commit()
        else:
            error = "Invalid friend username."

    # Get friend list
    friends_rows = conn.execute(
        'SELECT u.username FROM friends f JOIN users u ON f.friend_id = u.id WHERE f.user_id = ?', (user_id,)
    ).fetchall()
    friends_list = [row['username'] for row in friends_rows]
    conn.close()
    return render_template('friends.html', username=username, friends=friends_list, error=error)

@app.route('/inbox')
def inbox():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    user_id = user['id']
    # Get all friends (DMs)
    friends_rows = conn.execute(
        'SELECT u.username FROM friends f JOIN users u ON f.friend_id = u.id WHERE f.user_id = ?', (user_id,)
    ).fetchall()
    friends_list = [row['username'] for row in friends_rows]
    conn.close()
    return render_template('inbox.html', username=username, friends=friends_list)

@app.route('/settings')
def settings():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dm/<friend_username>')
def dm(friend_username):
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    # For now, just show a placeholder DM chat page
    return render_template('dm.html', username=username, friend_username=friend_username)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        username = request.form.get('username')
        if not username:
            return redirect(url_for('login'))
        session['username'] = username
    else:
        username = session.get('username')
        if not username:
            return redirect(url_for('login'))
    # Fetch last 50 messages for chat history
    conn = get_db_connection()
    messages = conn.execute('SELECT username, msg, timestamp FROM messages ORDER BY id ASC LIMIT 50').fetchall()
    conn.close()
    return render_template('chat.html', username=username, messages=messages)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    connected_users.add(username)
    emit('user_joined', {'username': username, 'users': list(connected_users)}, broadcast=True)

@socketio.on('message')
def handle_message(msg):
    username = session.get('username', 'Anonymous')
    timestamp = datetime.now().strftime('%H:%M')
    # Save message to DB
    conn = get_db_connection()
    conn.execute('INSERT INTO messages (username, msg, timestamp) VALUES (?, ?, ?)', (username, msg, timestamp))
    conn.commit()
    conn.close()
    emit('message', {'msg': msg, 'username': username, 'timestamp': timestamp}, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    username = data['username']
    emit('user_typing', {'username': username}, broadcast=True, include_self=False)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username', 'Anonymous')
    if username in connected_users:
        connected_users.remove(username)
        emit('user_left', {'username': username, 'users': list(connected_users)}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

