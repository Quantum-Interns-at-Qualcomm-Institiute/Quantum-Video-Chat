import signal
import sys

import eventlet
import socketio

sio = socketio.Server()
app = socketio.WSGIApp(sio)
rooms = {}


def signal_handler(sig, frame):
    print()
    print("Disconnecting everyone...")
    for room, users in rooms.items():
        print(f"Disconnecting room '{room}'")
        for user in users:
            print(f"Disconnecting user '{user}'")
            sio.disconnect(user)
            disconnect(user)
    print("Shutting down")
    sys.exit(0)


@sio.on('connect')
def connect(sid, environ):
    print("Incoming Connection Request!")
    room_id = 'chat'
    sio.enter_room(sid, room_id)
    if room_id in rooms:
        rooms[room_id] += [sid]
    else:
        rooms[room_id] = [sid]


@sio.on('disconnect')
def disconnect(sid):
    for room, users in rooms.items():
        if sid in users:
            users.remove(sid)
            print(f"Removed user '{sid}' from room '{room}'")
            break


@sio.on('frame')
def ping(sid, data):
    print(f'I got a frame from {sid}!')
    room = sio.rooms(sid)
    room.remove(sid)

    users = len(rooms[room[0]])
    sio.emit('frame', {'sid': sid, 'frame': data['frame']}, room=room, skip_sid=sid if users > 1 else None)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    eventlet.wsgi.server(eventlet.listen(('localhost', 4334)), app)
