# PyCord

PyCord is a real-time chat application built with Python, Flask, and Socket.IO. It's designed to be a lightweight and self-hostable alternative to Discord, offering features like servers, channels, direct messaging, and voice chat.

## Features

*   **Servers and Channels:** Organize your communities with servers and text channels.
*   **Real-time Messaging:** Instant messaging with support for text and image uploads.
*   **Direct Messages:** Private one-on-one conversations with friends.
*   **Friends List:** Add friends, see their online status, and manage friend requests.
*   **User Profiles:** Customize your profile with an avatar.
*   **Voice Channels:** Join voice channels and chat with others in real-time using WebRTC.
*   **Responsive UI:** A clean and modern user interface that works on different screen sizes.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

*   Python 3.6+
*   pip

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/USERNAME/REPOSITORY.git
    cd pycord
    ```

2.  **Create a virtual environment (recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**

    ```bash
    python app.py
    ```

5.  Open your web browser and navigate to `http://127.0.0.1:5000` to use the application.

## How to Use

1.  **Register a new account:** Click on the "Register" link on the login page to create a new account.
2.  **Log in:** Log in with your username and password.
3.  **Create or join a server:** Click the "+" button in the server list to create a new server.
4.  **Create a channel:** Once you're in a server, click the "+" button next to "Channels" to create a new channel.
5.  **Start chatting:** Click on a channel to start sending and receiving messages.
6.  **Add friends:** Go to the "Add Friend" page to send friend requests to other users.
7.  **Direct message:** Click on a friend's name in the friends list to start a direct message conversation.

## Built With

*   [Flask](https://flask.palletsprojects.com/) - The web framework used
*   [Flask-SocketIO](https://flask-socketio.readthedocs.io/) - For real-time communication
*   [Eventlet](http://eventlet.net/) - For asynchronous services
*   [SQLite](https://www.sqlite.org/) - The database engine
*   [jQuery](https://jquery.com/) - For simplifying HTML DOM tree traversal and manipulation

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.
