import os
import json
import signal
import sys
from random import choices
from string import ascii_lowercase

import eventlet
import socketio

sio = socketio.Server()
app = socketio.WSGIApp(sio)
rooms = {}


@sio.on('connect')
def connect(sid, environ):
    print(f"Incoming connection from {sid}!")


# TODO: make "join" instead of "room"
@sio.on('room')
def on_room(sid, room):
    """
    Adds a connected client to a room and updates self-maintained list of rooms.
    """

    if len(room) < 1:
        room = None
        while room is None or room in rooms:
            room = ''.join(choices(ascii_lowercase, k=5))

    if room in rooms:
        rooms[room] += [sid]
    else:
        print(f"Created new room {room}")
        rooms[room] = [sid]

    sio.enter_room(sid, room)
    print(f"Added {sid} to {room}")
    sio.emit("room", room, sid)


@sio.on('leave')
def on_leave(sid):
    """
    Removes a user from a room but maintains server connection. Assumes user is
    only in one room.

    Arguments:
        sid -- socket id for the request origin
    """
    # TODO: user should not be able to leave room they are not in; user should not
    #       be able to join multiple rooms
    for room, clients in rooms.items():
        if sid in clients:
            clients.remove(sid)
            sio.leave_room(sid, room)
            print(f"Removed client '{sid}' from room '{room}'")
            break


@sio.on('disconnect')
def disconnect(sid):
    print(f"User {sid} has disconnected from the server")


@sio.on('frame')
def handle_frame(sid, data):
    """
    Receives a frame from a client and emits it to all other clients in their room.
    If sender is the only client in their room, returns frame to sender. 

    parameters (indexed through data):
    - frame: Frame data # TODO: "frame" data doesnt say what's inside of the dict, i need to add kv

    emits:
    - sid: SID of sender
    - frame: Frame data
    """
    print(f'I got a frame from {sid}!')
    # Gets user's rooms and removes the default "room"– assumes user is only in 'chat' room
    room = sio.rooms(sid)
    room.remove(sid)

    skip = None

    if len(rooms[room[0]]) > 1:
        skip = sid
        data['sender'] = sid

    sio.emit('frame', data, room=room, skip_sid=skip)


if __name__ == '__main__':
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

    # Get binding address from config
    with open(file="server_config.json") as json_data:
        config = json.load(json_data)
        address = 'localhost' if 'address' not in config else config['address']
        port = 7777 if 'port' not in config else config['port']


    signal.signal(signal.SIGINT, sigint_handler)

    # Doesn't look like eventlet lets you just turn off logging.
    # Instead, redirected to some random place per:
    # https://stackoverflow.com/questions/75913952/how-to-disable-eventlet-logging-python
    eventlet.wsgi.server(eventlet.listen((config['address'], config['port'])), app, log=open(os.devnull,"w"))
