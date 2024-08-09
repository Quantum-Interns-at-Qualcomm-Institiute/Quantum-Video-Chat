import eventlet
import socketio

sio = socketio.Server()
app = socketio.WSGIApp(sio)


@sio.on("connect")
def on_connect(sid, environ):
    print("Backend connection established")


@sio.on("disconnect")
def on_disconnect(sid):
    print("Backend connection severed")


@sio.on("join_room")
def on_join_room(sid, new: bool):
    print(f"Request to {"create a new" if new else "join chat"} room")
    sio.emit("room", data="chat" if not new else "", skip_sid=sid)


@sio.on("room")
def on_room(sid, room):
    print(f"We got room ID {room}")


if __name__ == "__main__":
    eventlet.wsgi.server(eventlet.listen(("localhost", 5000)), app)
