import json
import signal
import sys

import eventlet
import socketio

sio = socketio.Server()
app = socketio.WSGIApp(sio)
rooms = {}


def sigint_handler(sig, frame):
    """
    Iterates through self-maintained list of rooms and disconnects all clients.

    NOTE: This function should only be called to handle a SIGINT
    """
    print()
    print("Disconnecting everyone...")
    for room, clients in rooms.items():
        print(f"Disconnecting room '{room}'")
        for client in clients:
            print(f"Disconnecting client '{client}'")
            sio.disconnect(client)
            disconnect(client)
    print("Shutting down")
    sys.exit(0)


@sio.on('connect')
def connect(sid, environ):
    """
    On connection, adds connected client to a room and updates self-maintained list
    of rooms.

    TODO: Rooms should not all be 'chat', but should instead be dynamically
    created at request of the client
    """
    print("Incoming Connection Request!")
    room_id = 'chat'
    sio.enter_room(sid, room_id)
    if room_id in rooms:
        rooms[room_id] += [sid]
    else:
        rooms[room_id] = [sid]


@sio.on('disconnect')
def disconnect(sid):
    """
    On disconnect, removes disconnected client from self-maintained list of rooms
    """
    for room, clients in rooms.items():
        if sid in clients:
            clients.remove(sid)
            print(f"Removed client '{sid}' from room '{room}'")
            break


@sio.on('frame')
def handle_frame(sid, data):
    """
    Receives a frame from a client and emits it to all other clients in their room.
    If sender is the only client in their room, returns frame to sender.

    parameters (indexed through data):
    - frame: Frame data

    emits:
    - sid: SID of sender
    - frame: Frame data
    """
    print(f'I got a frame from {sid}!')
    room = sio.rooms(sid)
    room.remove(sid)

    skip = None

    if len(rooms[room[0]]) > 1:
        skip = sid
        data['sender'] = sid

    sio.emit('frame', data, room=room, skip_sid=skip)


if __name__ == '__main__':
    CONFIG = "server_config.json"
    with open(file=CONFIG) as json_data:
        config = json.load(json_data)
        address = 'localhost' if 'address' not in config else config['address']
        port = 7777 if 'port' not in config else config['port']

    signal.signal(signal.SIGINT, sigint_handler)
    eventlet.wsgi.server(eventlet.listen((config['address'], config['port'])), app)
