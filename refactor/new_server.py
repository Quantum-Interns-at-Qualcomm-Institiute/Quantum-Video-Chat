import json
import signal
import sys
import os
from random import choices
from string import ascii_lowercase

import eventlet
import socketio

sio = socketio.Server()
app = socketio.WSGIApp(sio)
rooms = {}


@sio.on('connect')
def connect(sid, environ):
    """Logs incoming connection from client
    
    Parameters:
    - sid (str): socket id for the request origin
    """

    print(f"Incoming connection from client '{sid}'")


@sio.on('join-room')
def on_room(sid, room_id=None):
    """
    Adds a connected client to a room and updates self-maintained list of rooms.

    Parameters:
    - room_id (str, optional): Room client would like to join.

    Emits:
    - sid (str): socket id for the request origin
    - room_id (str): Confirmation of room client was put into. 
    """
    print(f"Client '{sid}' requests to join {'room \'' + str(room_id) + '\'' if room_id else 'new room'}.")

    # TODO: Throw error if user is already in a room.

    if not room_id:
        # If room_id not provided, generate a unique one
        # and initialize it in `rooms`
        while room_id is None or room_id in rooms:
            room_id = ''.join(choices(ascii_lowercase, k=5))
        print(f"Generated new room '{room_id}'")
        rooms[room_id] = []
    else:
        # If room_id was specified, confirm it is valid
        # (Users should be aware if the ID they typed is not what they intended)
        if room_id not in rooms:
            print("WARNING - Provided room_id doesn't exist.")
            return "Provided room_id doesn't exist."

    sio.enter_room(sid, room_id)
    rooms[room_id] += [sid]
    print(f"Added client '{sid}' to room '{room_id}'")
    sio.emit('room-id', room_id, to=sid)


@sio.on('leave-room')
def on_leave(sid):
    """
    Removes a user from a room but maintains server connection. Assumes user is
    only in one room.

    Parameters:
    - sid (str): socket id for the request origin
    """
    # TODO: user should not be able to leave room they are not in; user should not
    #       be able to join multiple rooms
    for room, clients in rooms.items():
        if sid in clients:
            print(f"Removing client '{sid}' from room '{room}'")
            sio.leave_room(sid, room)
            clients.remove(sid)

            if len(clients) == 0:
                print(f"Deleting empty room '{room}'.")
                del rooms[room]

            break


@sio.on('disconnect')
def disconnect(sid):
    """
    Log client disconnects.

    Parameters:
    - sid (str): socket id for the request origin
    """
    print(f"User '{sid}' has disconnected from the server")


@sio.on('frame')
def handle_frame(sid, data):
    """
    Receives a frame from a client and emits it to all other clients in their room.
    If sender is the only client in their room, returns frame to sender. 

    parameters (indexed through data):
    - frame: Frame data # TODO: "frame" data doesnt say what's inside of the dict, i need to add kv

    emits:
    - sid (str): SID of sender
    - frame: Frame data
    """
    print(f"I got a frame from client '{sid}'!")
    # Gets user's rooms and removes the default "room"– assumes user is only in 'chat' room
    room = sio.rooms(sid)
    room.remove(sid)
    if len(room) == 0:
        print(f"WARNING - Received a frame from a client in no rooms.")
        return "Client sent a frame when not in an active room."

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

        Parameters:
        - sig:
        - frame:
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
