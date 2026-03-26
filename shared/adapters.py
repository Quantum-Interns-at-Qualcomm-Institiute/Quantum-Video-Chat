"""Abstract adapter interfaces between middleware and frontend."""

from abc import ABC, abstractmethod


class VideoSink(ABC):
    """Interface for pushing video frames to the frontend."""

    @abstractmethod
    def send_frame(self, data: bytes) -> None:
        """Push a raw video frame to the frontend."""

    @abstractmethod
    def send_self_frame(self, data: bytes, width: int, height: int) -> None:
        """Push a raw RGBA self-video frame to the frontend for local preview."""


class StatusSink(ABC):
    """Interface for connection lifecycle events and status updates."""

    @abstractmethod
    def on_peer_id(self, callback) -> None:
        """Register *callback* for peer connection requests from the frontend.

        *callback* is called with a peer ID string whenever the frontend
        instructs the middleware to initiate a peer connection.
        """

    @abstractmethod
    def send_status(self, event: str, data: dict | None = None) -> None:
        """Push a named status event to the frontend.

        *event* is a short string such as ``'server_connected'`` or
        ``'peer_incoming'``.  *data* is an optional dict of extra fields.
        Implementations should be safe to call even when the transport is not
        yet connected (drop silently in that case).
        """


class FrontendAdapter(VideoSink, StatusSink):
    """Full interface between the middleware and the frontend process.

    Combines VideoSink and StatusSink. Existing code that type-hints
    FrontendAdapter continues to work unchanged.
    """
