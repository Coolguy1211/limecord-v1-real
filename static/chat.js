const socket = io();
let currentServerId = null;
let currentChannelId = null;
let localStream = null;
const peerConnections = {};
const config = {
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

socket.on('connect', () => {
    console.log('Connected to server');
});

// Link to create server page
document.getElementById('create-server-link').onclick = (e) => {
    e.preventDefault();
    window.location.href = "/create-server";
};


document.getElementById('add-channel-btn').onclick = () => {
    if (currentServerId) {
        const channelName = prompt("Enter new channel name:");
        if (channelName) {
            const channelType = prompt("Enter channel type (text or voice):", "text");
            if (channelType === 'text' || channelType === 'voice') {
                socket.emit('create_channel', { server_id: currentServerId, name: channelName, type: channelType });
            } else {
                alert("Invalid channel type. Please enter 'text' or 'voice'.");
            }
        }
    } else {
        alert("Please select a server first.");
    }
};

document.getElementById('profile-link').onclick = (e) => {
    e.preventDefault();
    // The server knows the username from the session
    window.location.href = `/user/${USERNAME}`;
};

document.getElementById('message-form').onsubmit = (e) => {
    e.preventDefault();
    sendMessage();
};

document.getElementById('upload-btn').onclick = () => {
    document.getElementById('fileUpload').click();
};

document.getElementById('fileUpload').onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            socket.emit('upload', {
                filename: file.name,
                data: event.target.result
            });
        };
        reader.readAsArrayBuffer(file);
    }
};

let currentDmFriend = null;

function sendMessage() {
    const messageInput = document.getElementById('myMessage');
    if (messageInput.value) {
        if (currentDmFriend) {
            socket.emit('send_dm', { message: messageInput.value });
        } else {
            socket.send(messageInput.value);
        }
        messageInput.value = '';
    }
}

// Socket listeners
socket.on('dm_history', (data) => {
    currentDmFriend = data.friend;
    currentChannelId = null;
    document.getElementById('channel-name-display').innerText = `DM with ${data.friend}`;
    const messagesUl = document.getElementById('messages');
    messagesUl.innerHTML = '';
    data.messages.forEach(addMessage);
});

socket.on('new_dm', (data) => {
    // Only add if it's part of the current conversation
    if (currentDmFriend && (data.user === currentDmFriend || data.user === USERNAME)) {
        addMessage(data);
    }
});
socket.on('server_list', (servers) => {
    const serversDiv = document.getElementById('servers');
    serversDiv.innerHTML = '';
    servers.forEach(server => {
        const serverDiv = document.createElement('div');
        serverDiv.className = 'server-icon';
        if (server.icon_url) {
            const img = document.createElement('img');
            img.src = server.icon_url;
            img.alt = server.name;
            serverDiv.appendChild(img);
        } else {
            serverDiv.innerText = server.name.substring(0, 1).toUpperCase();
        }
        serverDiv.dataset.serverId = server.id;
        serverDiv.dataset.serverName = server.name;
        serverDiv.onclick = () => {
            currentServerId = server.id;
            document.getElementById('server-name-display').innerText = server.name;
            socket.emit('get_channels', server.id);
        };
        serversDiv.appendChild(serverDiv);
    });
});

socket.on('server_created', (data) => {
    // dynamically add the new server to the list
    const serversDiv = document.getElementById('servers');
    const serverDiv = document.createElement('div');
    serverDiv.className = 'server-icon';
    if (data.icon_url) {
        const img = document.createElement('img');
        img.src = data.icon_url;
        img.alt = data.server_name;
        serverDiv.appendChild(img);
    } else {
        serverDiv.innerText = data.server_name.substring(0, 1).toUpperCase();
    }
    serverDiv.dataset.serverId = data.server_id;
    serverDiv.dataset.serverName = data.server_name;
    serverDiv.onclick = () => {
        currentServerId = data.server_id;
        document.getElementById('server-name-display').innerText = data.server_name;
        socket.emit('get_channels', data.server_id);
    };
    serversDiv.appendChild(serverDiv);
});

socket.on('channel_list', (channels) => {
    const channelsUl = document.getElementById('channels');
    channelsUl.innerHTML = '';
    channels.forEach(channel => {
        const li = document.createElement('li');
        li.dataset.channelId = channel.id;
        li.dataset.channelName = channel.name;
        li.dataset.channelType = channel.type;

        if (channel.type === 'voice') {
            li.innerHTML = `🔊 ${channel.name} <button>Join</button>`;
        } else {
            li.innerText = `# ${channel.name}`;
        }
        channelsUl.appendChild(li);
    });
});

socket.on('history', (messages) => {
    const messagesUl = document.getElementById('messages');
    messagesUl.innerHTML = '';
    messages.forEach(addMessage);
});

socket.on('message', (data) => {
    addMessage(data);
});

function addMessage(data) {
    const messagesUl = document.getElementById('messages');
    const li = document.createElement('li');
    li.className = 'message';

    const avatarImg = document.createElement('img');
    avatarImg.src = data.avatar_url || '/static/default-avatar.png';
    avatarImg.className = 'avatar';
    li.appendChild(avatarImg);

    const messageContentDiv = document.createElement('div');
    messageContentDiv.className = 'message-content';

    const userSpan = document.createElement('span');
    userSpan.className = 'username';
    userSpan.innerText = data.user;
    messageContentDiv.appendChild(userSpan);

    if (data.is_image) {
        const img = document.createElement('img');
        img.src = data.message;
        messageContentDiv.appendChild(img);
    } else if (data.filename) { // It's a file, not a regular message
        const fileLink = document.createElement('a');
        fileLink.href = data.message;
        fileLink.innerText = data.filename;
        fileLink.target = "_blank"; // Open in new tab
        fileLink.className = 'file-link';
        messageContentDiv.appendChild(fileLink);
    }
    else {
        const messageSpan = document.createElement('span');
        messageSpan.className = 'message-text';
        messageSpan.innerText = data.message;
        messageContentDiv.appendChild(messageSpan);
    }
    li.appendChild(messageContentDiv);
    messagesUl.appendChild(li);
    messagesUl.scrollTop = messagesUl.scrollHeight;
}

socket.on('friend_list', (friends) => {
    const friendsUl = document.getElementById('friends');
    friendsUl.innerHTML = '';
    friends.forEach(friend => {
        const li = document.createElement('li');
        li.dataset.friendUsername = friend.username;
        const statusIndicator = document.createElement('span');
        statusIndicator.className = `status-indicator ${friend.status}`;
        li.appendChild(statusIndicator);
        const friendName = document.createTextNode(friend.username);
        li.appendChild(friendName);
        li.onclick = () => {
            socket.emit('open_dm', friend.username);
        };
        friendsUl.appendChild(li);
    });
});

socket.on('status_change', (data) => {
    const friendLi = document.querySelector(`[data-friend-username="${data.username}"]`);
    if (friendLi) {
        const statusIndicator = friendLi.querySelector('.status-indicator');
        statusIndicator.className = `status-indicator ${data.status}`;
    }
});

socket.on('friend_requests', (requests) => {
    const requestsUl = document.getElementById('friend-requests');
    requestsUl.innerHTML = '';
    requests.forEach(request => {
        const li = document.createElement('li');
        li.innerText = request.username;
        const acceptBtn = document.createElement('button');
        acceptBtn.innerText = 'Accept';
        acceptBtn.onclick = () => {
            socket.emit('accept_friend_request', request.id);
        };
        li.appendChild(acceptBtn);
        requestsUl.appendChild(li);
    });
});

socket.on('friend_request_sent', (data) => {
    alert(data.message);
});

socket.on('error', (data) => {
    alert(data.message);
});

// WebRTC Implementation
// The following code handles the WebRTC connections for voice and video chat.
// It uses Socket.IO for signaling to establish peer-to-peer connections.
// The implementation includes creating peer connections, handling ICE candidates,
// creating offers and answers, and managing media streams.
// WebRTC Listeners
socket.on('user_joined_voice', (data) => {
    console.log('user joined voice', data);
    createPeerConnection(data.sid, true);
});

socket.on('user_left_voice', (data) => {
    console.log('user left voice', data);
    if (peerConnections[data.sid]) {
        peerConnections[data.sid].close();
        delete peerConnections[data.sid];
        const videoElement = document.getElementById(data.sid);
        if (videoElement) {
            videoElement.remove();
        }
    }
});

socket.on('offer', async (data) => {
    if (!peerConnections[data.sid]) {
        createPeerConnection(data.sid, false);
    }
    await peerConnections[data.sid].setRemoteDescription(new RTCSessionDescription(data.offer));
    const answer = await peerConnections[data.sid].createAnswer();
    await peerConnections[data.sid].setLocalDescription(answer);
    socket.emit('answer', { target_sid: data.sid, answer: answer });
});

socket.on('answer', async (data) => {
    await peerConnections[data.sid].setRemoteDescription(new RTCSessionDescription(data.answer));
});

socket.on('ice_candidate', (data) => {
    peerConnections[data.sid].addIceCandidate(new RTCIceCandidate(data.candidate));
});

async function startMedia() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
        addVideoStream('local-video', localStream);
    } catch (e) {
        console.error('Error getting user media', e);
    }
}

function createPeerConnection(sid, is_offerer) {
    peerConnections[sid] = new RTCPeerConnection(config);
    peerConnections[sid].onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit('ice_candidate', { target_sid: sid, candidate: event.candidate });
        }
    };
    peerConnections[sid].ontrack = (event) => {
        addVideoStream(sid, event.streams[0]);
    };
    if (localStream) {
        localStream.getTracks().forEach(track => {
            peerConnections[sid].addTrack(track, localStream);
        });
    }
    if (is_offerer) {
        peerConnections[sid].createOffer()
            .then(offer => peerConnections[sid].setLocalDescription(offer))
            .then(() => {
                socket.emit('offer', { target_sid: sid, offer: peerConnections[sid].localDescription });
            });
    }
}

function addVideoStream(id, stream) {
    const videoGrid = document.getElementById('video-grid');
    const video = document.createElement('video');
    video.id = id;
    video.srcObject = stream;
    video.autoplay = true;
    video.muted = id === 'local-video'; // Mute self
    videoGrid.appendChild(video);
}

// Modify the join voice channel to start media
const originalJoinVoice = (channel) => {
    console.log('Joining voice channel', channel.id);
    document.getElementById('video-grid').style.display = 'grid';
    document.getElementById('voice-controls').style.display = 'flex';
    startMedia().then(() => {
        socket.emit('join_voice_channel', { channel_id: channel.id });
    });
};

// Use event delegation for channel list clicks
document.getElementById('channels').addEventListener('click', (e) => {
    const target = e.target;
    const li = target.closest('li[data-channel-id]');
    if (!li) return;

    const channelId = li.dataset.channelId;
    const channelName = li.dataset.channelName;
    const channelType = li.dataset.channelType;

    if (target.tagName === 'BUTTON' && channelType === 'voice') {
        e.stopPropagation();
        originalJoinVoice({ id: channelId, name: channelName });
    } else if (channelType === 'text') {
        currentChannelId = channelId;
        currentDmFriend = null;
        document.getElementById('channel-name-display').innerText = channelName;
        socket.emit('join_channel', channelId);
    }
});

document.getElementById('share-screen-btn').onclick = async () => {
    if (!localStream) {
        alert("You must be in a voice channel to share your screen.");
        return;
    }
    const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    const screenTrack = screenStream.getVideoTracks()[0];
    const videoTrack = localStream.getVideoTracks()[0];
    for (const sid in peerConnections) {
        const sender = peerConnections[sid].getSenders().find(s => s.track.kind === 'video');
        sender.replaceTrack(screenTrack);
    }
    localStream.removeTrack(videoTrack);
    localStream.addTrack(screenTrack);
    const localVideo = document.getElementById('local-video');
    localVideo.srcObject = localStream;

    screenTrack.onended = () => {
        // Stop sharing and revert to webcam
        for (const sid in peerConnections) {
            const sender = peerConnections[sid].getSenders().find(s => s.track.kind === 'video');
            sender.replaceTrack(videoTrack);
        }
        localStream.removeTrack(screenTrack);
        localStream.addTrack(videoTrack);
        localVideo.srcObject = localStream;
    };
};

document.getElementById('leave-voice-btn').onclick = () => {
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        localStream = null;
    }
    for (const sid in peerConnections) {
        peerConnections[sid].close();
        delete peerConnections[sid];
    }
    const videoGrid = document.getElementById('video-grid');
    videoGrid.innerHTML = '';
    videoGrid.style.display = 'none';
    document.getElementById('voice-controls').style.display = 'none';
    if (currentChannelId) {
        socket.emit('leave_voice_channel', { channel_id: currentChannelId });
    }
};

// Modal handling
const modal = document.getElementById('user-settings-modal');
const settingsBtn = document.getElementById('settings-btn');
const closeBtn = document.querySelector('.close-button');

settingsBtn.onclick = () => {
    modal.style.display = 'block';
};

closeBtn.onclick = () => {
    modal.style.display = 'none';
};

window.onclick = (event) => {
    if (event.target == modal) {
        modal.style.display = 'none';
    }
};

document.getElementById('status-selector').onclick = (event) => {
    if (event.target.tagName === 'BUTTON') {
        const status = event.target.dataset.status;
        socket.emit('change_status', status);
        modal.style.display = 'none';
    }
};
