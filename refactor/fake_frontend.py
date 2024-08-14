import argparse

import eventlet
import socketio
from eventlet import sleep

sio = socketio.Server()
app = socketio.WSGIApp(sio)


@sio.on("connect")
def on_connect(sid, environ):
    print("Backend connection established")


@sio.on("disconnect")
def on_disconnect(sid):
    print("Backend connection severed")


@sio.on("room")
def on_room(sid, room):
    print(f"We got room ID {room}")


@sio.on("frame")
def on_frame(sid, data):
    """
    Takes a frame sent from the python socket and puts it into rendering process

    Arguments:
        sid -- _description_
        data -- {
                    'frame' : bytes -- RGBA encoded frame data
                    'self'  : bool  -- True means user's own frame
                }
    """
    print(f"{"Me" if data['self'] else "Them"}: {data['frame'][:10]}...")


@sio.on("leave")
def on_leave(sid):
    print("User needs to leave the room")
    # TODO: stop video thread, navigate back onto the main screen, restart trying to connect to the server again

# MOCKED EVENTS


@sio.on("join_room")
def on_join_room(sid, new: bool):
    print(f"User wants to {"create a new" if new else "join 'chat'"} room")
    sio.emit("room", data="chat" if not new else "", skip_sid=sid)


@sio.on("leave_room")
def on_leave_room(sid):
    print("User wants to leave their room")
    sio.emit("leave")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Required
    required = parser.add_argument_group('Required')
    mode_group = required.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('-s', '--server', action='store_true', help='Host a bouncer server')
    mode_group.add_argument('-c', '--client', action='store_true', help='Connect to a pre-existing server')

    args = parser.parse_args()

    if args.server:
        eventlet.wsgi.server(eventlet.listen(("localhost", 5000)), app)
    else:
        # TODO: where should this go
        def safe_connect(sio, address, port, label, retries=10, wait=15):
            for retry in range(retries):
                try:
                    sio.connect(f"http://{address}:{port}", wait=True)
                    break
                except Exception:
                    if retries - retry >= 0:
                        print(f"Connection to {label} failed, trying again in {wait} seconds, {retries - retry} more time(s)")
                        for i in range(1, wait + 1):
                            print(f"{i}")
                            sleep(1)
                    else:
                        print("Connection failed too many times, exiting gracefully")
                        # TODO: figure out how to exit gracefully

        sio = socketio.Client()
        safe_connect(sio, 'localhost', 5000, '')

        input("Ready to join a room...")
        sio.emit("join_room", True)

        input("Ready to leave the room...")
        sio.emit("leave_room")

        input("Ready to join room 'chat'")
        sio.emit("join_room", False)

        input("Ready to close...")
        sio.disconnect()
