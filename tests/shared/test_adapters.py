"""Tests for shared/adapters.py — FrontendAdapter, VideoSink, StatusSink ABCs."""
import pytest
from shared.adapters import FrontendAdapter, VideoSink, StatusSink


class TestVideoSink:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            VideoSink()

    def test_video_only_implementation(self):
        class VideoOnly(VideoSink):
            def send_frame(self, data):
                pass
            def send_self_frame(self, data, width, height):
                pass

        adapter = VideoOnly()
        assert isinstance(adapter, VideoSink)


class TestStatusSink:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            StatusSink()

    def test_status_only_implementation(self):
        class StatusOnly(StatusSink):
            def on_peer_id(self, callback):
                pass
            def send_status(self, event, data=None):
                pass

        adapter = StatusOnly()
        assert isinstance(adapter, StatusSink)


class TestFrontendAdapter:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            FrontendAdapter()

    def test_partial_implementation_raises(self):
        class PartialAdapter(FrontendAdapter):
            def send_frame(self, data):
                pass
            def send_self_frame(self, data, width, height):
                pass

        with pytest.raises(TypeError):
            PartialAdapter()

    def test_complete_implementation_works(self):
        class CompleteAdapter(FrontendAdapter):
            def send_frame(self, data):
                pass
            def send_self_frame(self, data, width, height):
                pass
            def on_peer_id(self, callback):
                pass
            def send_status(self, event, data=None):
                pass

        adapter = CompleteAdapter()
        assert isinstance(adapter, FrontendAdapter)
        assert isinstance(adapter, VideoSink)
        assert isinstance(adapter, StatusSink)

    def test_missing_send_frame_raises(self):
        class MissingSendFrame(FrontendAdapter):
            def send_self_frame(self, data, width, height):
                pass
            def on_peer_id(self, callback):
                pass
            def send_status(self, event, data=None):
                pass

        with pytest.raises(TypeError):
            MissingSendFrame()
