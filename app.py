from flask import Flask, render_template, request, send_from_directory, session, redirect, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import eventlet
import sqlite3
import uuid
import os
import mimetypes
import updater

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
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS server_members (id INTEGER PRIMARY KEY, user_id INTEGER, server_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(server_id) REFERENCES servers(id))")
        cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY, name TEXT, server_id INTEGER, type TEXT DEFAULT 'text', FOREIGN KEY(server_id) REFERENCES servers(id))")
        try:
            cursor.execute("ALTER TABLE channels ADD COLUMN type TEXT DEFAULT 'text'")
        except:
            pass
        cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, user_id INTEGER, channel_id INTEGER, message TEXT, is_image BOOLEAN, filename TEXT, FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(channel_id) REFERENCES channels(id))")
        # Add filename column if it doesn't exist for backward compatibility
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN filename TEXT")
        except:
            pass # Column already exists
        cursor.execute("CREATE TABLE IF NOT EXISTS friends (id INTEGER PRIMARY KEY, user1_id INTEGER, user2_id INTEGER, status TEXT, FOREIGN KEY(user1_id) REFERENCES users(id), FOREIGN KEY(user2_id) REFERENCES users(id))")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS direct_messages (
                id INTEGER PRIMARY KEY,
                sender_id INTEGER,
                receiver_id INTEGER,
                message TEXT,
                is_image BOOLEAN DEFAULT FALSE,
                filename TEXT,
                FOREIGN KEY(sender_id) REFERENCES users(id),
                FOREIGN KEY(receiver_id) REFERENCES users(id)
            )
        """)
        conn.commit()

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[1], password):
                session["user_id"] = user[0]
                session["username"] = username
                return redirect(url_for("chat"))
        return "Invalid username or password"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, generate_password_hash(password)))
                conn.commit()
            except sqlite3.IntegrityError:
                return "Username already taken"
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/chat")
def chat():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("chat.html")

@app.route("/create-server")
def create_server_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("create_server.html")

@app.route("/user/<username>")
def profile_page(username):
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("profile.html", username=username)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@socketio.on('connect')
def on_connect():
    if "user_id" in session:
        user_id = session["user_id"]
        username = session["username"]
        users[request.sid] = {"user_id": user_id, "username": username, "current_channel": None, "current_dm_partner": None}
        get_servers()
        get_friends_list()
        get_friend_requests()

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
        get_servers() # Refresh list for the user
        emit('server_created', {'server_id': server_id, 'server_name': server_name})

@socketio.on('get_channels')
def get_channels(server_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, type FROM channels WHERE server_id = ?", (server_id,))
        channels = [{"id": row[0], "name": row[1], "type": row[2]} for row in cursor.fetchall()]
        emit('channel_list', channels)

@socketio.on('create_channel')
def create_channel(data):
    if request.sid in users:
        server_id = data['server_id']
        channel_name = data['name']
        channel_type = data.get('type', 'text')
        # Verify user is a member of the server before creating a channel
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM server_members WHERE user_id = ? AND server_id = ?", (user_id, server_id))
            if cursor.fetchone():
                cursor.execute("INSERT INTO channels (name, server_id, type) VALUES (?, ?, ?)", (channel_name, server_id, channel_type))
                conn.commit()
                # Broadcast to all members of the server
                # A more optimized approach would be to have a room for each server
                get_channels(server_id) # For now, just refresh for the creator

@socketio.on('join_channel')
def join_channel(channel_id):
    if request.sid in users:
        if users[request.sid]['current_channel']:
            leave_room(users[request.sid]['current_channel'])
        join_room(channel_id)
        users[request.sid]['current_channel'] = channel_id
        users[request.sid]['current_dm_partner'] = None  # Not in a DM
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT u.username, m.message, m.is_image, m.filename FROM messages m JOIN users u ON m.user_id = u.id WHERE m.channel_id = ? ORDER BY m.id ASC", (channel_id,))
            messages = [{"user": row[0], "message": row[1], "is_image": row[2], "filename": row[3]} for row in cursor.fetchall()]
            emit('history', messages)

@socketio.on('open_dm')
def open_dm(friend_username):
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (friend_username,))
            friend = cursor.fetchone()
            if friend:
                friend_id = friend[0]
                users[request.sid]['current_dm_partner'] = friend_id
                users[request.sid]['current_channel'] = None # Not in a channel
                cursor.execute("""
                    SELECT u.username, dm.message, dm.is_image, dm.filename
                    FROM direct_messages dm JOIN users u ON dm.sender_id = u.id
                    WHERE (dm.sender_id = ? AND dm.receiver_id = ?) OR (dm.sender_id = ? AND dm.receiver_id = ?)
                    ORDER BY dm.id ASC
                """, (user_id, friend_id, friend_id, user_id))
                messages = [{"user": row[0], "message": row[1], "is_image": row[2], "filename": row[3]} for row in cursor.fetchall()]
                emit('dm_history', {'friend': friend_username, 'messages': messages})

@socketio.on('send_dm')
def send_dm(data):
    if request.sid in users and users[request.sid]['current_dm_partner']:
        sender_id = users[request.sid]['user_id']
        receiver_id = users[request.sid]['current_dm_partner']
        message = data['message']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO direct_messages (sender_id, receiver_id, message, is_image) VALUES (?, ?, ?, ?)",
                           (sender_id, receiver_id, message, False))
            conn.commit()

        # Find the recipient's sid to send them the message in real-time
        recipient_sid = None
        for sid, user_info in users.items():
            if user_info['user_id'] == receiver_id:
                recipient_sid = sid
                break

        new_message = {"user": users[request.sid]['username'], "message": message, "is_image": False}
        if recipient_sid:
            emit('new_dm', new_message, to=recipient_sid)
        # also send to self
        emit('new_dm', new_message)

@socketio.on("message")
def handle_message(msg):
    if request.sid in users:
        user_info = users[request.sid]
        if user_info['current_dm_partner']:
            send_dm({'message': msg})
        elif user_info['current_channel']:
            channel_id = user_info['current_channel']
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO messages (user_id, channel_id, message, is_image) VALUES (?, ?, ?, ?)", (user_info['user_id'], channel_id, msg, False))
                conn.commit()
            send({"user": user_info['username'], "message": msg, "is_image": False}, to=channel_id)

@socketio.on('upload')
def handle_upload(file_data):
    if request.sid in users:
        user_info = users[request.sid]
        original_filename = file_data['filename']
        file_bytes = file_data['data']
        file_ext = os.path.splitext(original_filename)[1]
        saved_filename = f"{uuid.uuid4()}{file_ext}"
        filepath = os.path.join(UPLOADS_DIR, saved_filename)
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        file_url = f"/uploads/{saved_filename}"
        mimetype, _ = mimetypes.guess_type(filepath)
        is_image = mimetype and mimetype.startswith('image/')

        if user_info['current_dm_partner']:
            sender_id = user_info['user_id']
            receiver_id = user_info['current_dm_partner']
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO direct_messages (sender_id, receiver_id, message, is_image, filename) VALUES (?, ?, ?, ?, ?)",
                               (sender_id, receiver_id, file_url, is_image, original_filename))
                conn.commit()

            recipient_sid = None
            for sid, u_info in users.items():
                if u_info['user_id'] == receiver_id:
                    recipient_sid = sid
                    break

            new_message = {"user": user_info['username'], "message": file_url, "is_image": is_image, "filename": original_filename}
            if recipient_sid:
                emit('new_dm', new_message, to=recipient_sid)
            emit('new_dm', new_message)

        elif user_info['current_channel']:
            channel_id = user_info['current_channel']
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO messages (user_id, channel_id, message, is_image, filename) VALUES (?, ?, ?, ?, ?)",
                               (user_info['user_id'], channel_id, file_url, is_image, original_filename))
                conn.commit()
            send({"user": user_info['username'], "message": file_url, "is_image": is_image, "filename": original_filename}, to=channel_id)

@socketio.on('disconnect')
def on_disconnect():
    if request.sid in users:
        for channel_id, sids in voice_channels.items():
            if request.sid in sids:
                leave_voice_channel({'channel_id': channel_id})
        del users[request.sid]

@app.route("/add_friend", methods=["GET", "POST"])
def add_friend_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        friend_username = request.form["username"]
        user_id = session["user_id"]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (friend_username,))
            friend = cursor.fetchone()
            if friend:
                friend_id = friend[0]
                if user_id == friend_id:
                    # Using flash messages would be better here, but for now, just a simple response
                    return "You can't add yourself as a friend."
                cursor.execute("SELECT id FROM friends WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)", (user_id, friend_id, friend_id, user_id))
                if cursor.fetchone():
                    return "Friend request already sent or you are already friends."
                cursor.execute("INSERT INTO friends (user1_id, user2_id, status) VALUES (?, ?, ?)", (user_id, friend_id, 'pending'))
                conn.commit()
                return "Friend request sent."
            else:
                return "User not found."
    return render_template("add_friend.html")

@socketio.on('add_friend')
def add_friend(friend_username):
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (friend_username,))
            friend = cursor.fetchone()
            if friend:
                friend_id = friend[0]
                if user_id == friend_id:
                    emit('error', {'message': "You can't add yourself as a friend."})
                    return
                cursor.execute("SELECT id FROM friends WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)", (user_id, friend_id, friend_id, user_id))
                if cursor.fetchone():
                    emit('error', {'message': 'Friend request already sent or you are already friends.'})
                    return
                cursor.execute("INSERT INTO friends (user1_id, user2_id, status) VALUES (?, ?, ?)", (user_id, friend_id, 'pending'))
                conn.commit()
                emit('friend_request_sent', {'message': 'Friend request sent.'})
            else:
                emit('error', {'message': 'User not found.'})

@socketio.on('get_friends')
def get_friends_list():
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username FROM users u JOIN friends f ON u.id = f.user2_id WHERE f.user1_id = ? AND f.status = 'accepted'
                UNION
                SELECT u.username FROM users u JOIN friends f ON u.id = f.user1_id WHERE f.user2_id = ? AND f.status = 'accepted'
            """, (user_id, user_id))
            friends = [row[0] for row in cursor.fetchall()]
            emit('friend_list', friends)

@socketio.on('get_friend_requests')
def get_friend_requests():
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.id, u.username FROM friends f JOIN users u ON f.user1_id = u.id
                WHERE f.user2_id = ? AND f.status = 'pending'
            """, (user_id,))
            requests = [{"id": row[0], "username": row[1]} for row in cursor.fetchall()]
            emit('friend_requests', requests)

@socketio.on('accept_friend_request')
def accept_friend_request(request_id):
    if request.sid in users:
        user_id = users[request.sid]['user_id']
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Ensure the user is the recipient of the request
            cursor.execute("SELECT id FROM friends WHERE id = ? AND user2_id = ?", (request_id, user_id))
            if cursor.fetchone():
                cursor.execute("UPDATE friends SET status = 'accepted' WHERE id = ?", (request_id,))
                conn.commit()
                get_friends_list()
                get_friend_requests()

voice_channels = {}

@socketio.on('join_voice_channel')
def join_voice_channel(data):
    channel_id = data['channel_id']
    if request.sid in users:
        user_info = users[request.sid]
        if channel_id not in voice_channels:
            voice_channels[channel_id] = []

        # Notify others in the channel
        for sid in voice_channels[channel_id]:
            emit('user_joined_voice', {'sid': request.sid, 'username': user_info['username']}, to=sid)

        voice_channels[channel_id].append(request.sid)
        emit('voice_channel_participants', [users[sid]['username'] for sid in voice_channels[channel_id]])

@socketio.on('leave_voice_channel')
def leave_voice_channel(data):
    channel_id = data['channel_id']
    if request.sid in users and channel_id in voice_channels and request.sid in voice_channels[channel_id]:
        voice_channels[channel_id].remove(request.sid)
        for sid in voice_channels[channel_id]:
            emit('user_left_voice', {'sid': request.sid}, to=sid)

@socketio.on('offer')
def handle_offer(data):
    emit('offer', data, to=data['target_sid'])

@socketio.on('answer')
def handle_answer(data):
    emit('answer', data, to=data['target_sid'])

@socketio.on('ice_candidate')
def handle_ice_candidate(data):
    emit('ice_candidate', data, to=data['target_sid'])

@app.route("/update")
def update_app():
    updater.update_application()
    return "Checking for updates. See console for details."

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
