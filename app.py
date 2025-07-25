from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from datetime import datetime
import os
import sqlite3

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
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            msg TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/chat', methods=['POST'])
def chat():
    username = request.form.get('username')
    if not username:
        return redirect(url_for('login'))

    session['username'] = username
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

