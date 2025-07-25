from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'konnichiyabs-secret-key'
socketio = SocketIO(app)

# Simple in-memory user tracking
connected_users = set()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/chat', methods=['POST'])
def chat():
    username = request.form.get('username')
    if not username:
        return redirect(url_for('login'))

    session['username'] = username
    return render_template('chat.html', username=username)

@socketio.on('join')
def handle_join(data):
    username = data['username']
    connected_users.add(username)
    emit('user_joined', {'username': username, 'users': list(connected_users)}, broadcast=True)

@socketio.on('message')
def handle_message(msg):
    username = session.get('username', 'Anonymous')
    emit('message', {'msg': msg, 'username': username}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username', 'Anonymous')
    if username in connected_users:
        connected_users.remove(username)
        emit('user_left', {'username': username, 'users': list(connected_users)}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
