from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import eventlet
import sqlite3
import uuid
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

users = {}
DB_FILE = "database.db"
UPLOADS_DIR = "uploads"

def init_db():
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS server_members (id INTEGER PRIMARY KEY, user_id INTEGER, server_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(server_id) REFERENCES servers(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY, name TEXT, server_id INTEGER, FOREIGN KEY(server_id) REFERENCES servers(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, user_id INTEGER, channel_id INTEGER, message TEXT, is_image BOOLEAN, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(channel_id) REFERENCES channels(id))")
        conn.commit()

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@socketio.on('setUsername')
def set_username(username):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
        else:
            cursor.execute("INSERT INTO users (username) VALUES (?)", (username,))
            conn.commit()
            user_id = cursor.lastrowid
    users[request.sid] = {"user_id": user_id, "username": username, "current_channel": None}
    get_servers()

@socketio.on('get_servers')
def get_servers():
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT s.id, s.name FROM servers s JOIN server_members sm ON s.id = sm.server_id WHERE sm.user_id = ?", (user_id,))
            servers = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
            emit('server_list', servers)

@socketio.on('create_server')
def create_server(server_name):
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO servers (name) VALUES (?)", (server_name,))
            server_id = cursor.lastrowid
            cursor.execute("INSERT INTO server_members (user_id, server_id) VALUES (?, ?)", (user_id, server_id))
            cursor.execute("INSERT INTO channels (name, server_id) VALUES (?, ?)", ("#general", server_id))
            conn.commit()
        get_servers()

@socketio.on('get_channels')
def get_channels(server_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM channels WHERE server_id = ?", (server_id,))
        channels = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
        emit('channel_list', channels)

@socketio.on('join_channel')
def join_channel(channel_id):
    if request.sid in users:
        if users[request.sid]['current_channel']:
            leave_room(users[request.sid]['current_channel'])
        join_room(channel_id)
        users[request.sid]['current_channel'] = channel_id
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT u.username, m.message, m.is_image FROM messages m JOIN users u ON m.user_id = u.id WHERE m.channel_id = ? ORDER BY m.id ASC", (channel_id,))
            messages = [{"user": row[0], "message": row[1], "is_image": row[2]} for row in cursor.fetchall()]
            emit('history', messages)

@socketio.on("message")
def handle_message(msg):
    if request.sid in users and users[request.sid]['current_channel']:
        user_info = users[request.sid]
        channel_id = user_info['current_channel']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user_id, channel_id, message, is_image) VALUES (?, ?, ?, ?)", (user_info['user_id'], channel_id, msg, False))
            conn.commit()
        send({"user": user_info['username'], "message": msg, "is_image": False}, to=channel_id)

@socketio.on('image')
def handle_image(image_data):
    if request.sid in users and users[request.sid]['current_channel']:
        user_info = users[request.sid]
        channel_id = user_info['current_channel']
        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(UPLOADS_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        image_url = f"/uploads/{filename}"
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user_id, channel_id, message, is_image) VALUES (?, ?, ?, ?)", (user_info['user_id'], channel_id, image_url, True))
            conn.commit()
        send({"user": user_info['username'], "message": image_url, "is_image": True}, to=channel_id)

@socketio.on('disconnect')
def on_disconnect():
    if request.sid in users:
        del users[request.sid]

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
