import socketio

from shared.adapters import FrontendAdapter


class ElectronSocketAdapter(FrontendAdapter):
    """
    Bridges the middleware to an Electron frontend via a socket.io connection.

    - `send_frame` emits raw video bytes as a 'stream' event.
    - `on_peer_id` wires the 'connect_to_peer' socket event to a callback,
      decoupling the rest of the middleware from socket.io event registration.
    - `send_status` emits named status events so the UI can reflect connection
      state changes.  Safe to call even when the socket is not yet connected.
    """

    def __init__(self, socket: socketio.Client):
        self._socket = socket

    def send_frame(self, data: bytes) -> None:
        if self._socket.connected:
            try:
                self._socket.emit('stream', data)
            except Exception:
                pass  # Drop frame silently if the IPC socket is mid-reconnect

    def send_self_frame(self, data: bytes, width: int, height: int) -> None:
        if self._socket.connected:
            try:
                self._socket.emit('self-frame', {'frame': data, 'width': width, 'height': height})
            except Exception:
                pass  # Drop frame silently if the IPC socket is mid-reconnect

    def on_peer_id(self, callback) -> None:
        @self._socket.on('connect_to_peer')
        def _handler(data):
            callback(data)

    def send_status(self, event: str, data: dict = None) -> None:
        if self._socket.connected:
            self._socket.emit('status', {'event': event, 'data': data or {}})
