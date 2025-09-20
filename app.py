from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, send, emit
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                message TEXT NOT NULL,
                is_image BOOLEAN DEFAULT FALSE
            )
        """)
        conn.commit()

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)

@socketio.on('connect')
def on_connect():
    print("A user connected")
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user, message, is_image FROM messages ORDER BY id ASC")
        messages = [{"user": row[0], "message": row[1], "is_image": row[2]} for row in cursor.fetchall()]
        print(f"Sending history: {messages}")
        emit('history', messages)

@socketio.on('setUsername')
def set_username(username):
    users[request.sid] = username

@socketio.on("message")
def handle_message(msg):
    if request.sid in users:
        user = users[request.sid]
        print(f"Message from {user}: {msg}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user, message, is_image) VALUES (?, ?, ?)", (user, msg, False))
            conn.commit()
            print("Message stored in database")
        send({"user": user, "message": msg, "is_image": False}, broadcast=True)

@socketio.on('image')
def handle_image(image_data):
    if request.sid in users:
        user = users[request.sid]
        print(f"Image received from {user}")
        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(UPLOADS_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)

        image_url = f"/uploads/{filename}"
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (user, message, is_image) VALUES (?, ?, ?)", (user, image_url, True))
            conn.commit()
            print("Image message stored in database")

        send({"user": user, "message": image_url, "is_image": True}, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    if request.sid in users:
        del users[request.sid]

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
