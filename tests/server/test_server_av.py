"""Tests for server/utils/av.py — ServerVideoClientNamespace and AV class."""
from unittest.mock import MagicMock, patch


class TestServerVideoClientNamespace:
    def test_handle_received_frame_stores_in_cls_video(self):
        """_handle_received_frame should store the decoded frame in cls.video[user_id]."""
        from utils.av import ServerVideoClientNamespace

        mock_av = MagicMock()
        mock_av.video_shape = (480, 640, 3)

        ns = ServerVideoClientNamespace.__new__(ServerVideoClientNamespace)
        ns.av = mock_av
        ns.cls = MagicMock()
        ns.cls.video = {}

        import numpy as np
        frame_data = np.zeros((480, 640, 3), dtype="uint8").tobytes()
        ns._handle_received_frame("user1", frame_data)

        assert "user1" in ns.cls.video
        assert ns.cls.video["user1"].shape == (480, 640, 3)

    def test_tobytes_converts_to_raw(self):
        """_tobytes should return raw bytes from numpy array."""
        from utils.av import ServerVideoClientNamespace

        ns = ServerVideoClientNamespace.__new__(ServerVideoClientNamespace)
        import numpy as np
        image = np.zeros((10, 10, 3), dtype="uint8")
        result = ns._tobytes(image)
        assert isinstance(result, bytes)
        assert len(result) == 10 * 10 * 3


class TestAV:
    @patch("utils.av._keygen_name", "DEBUG")
    @patch("utils.av.Thread")
    def test_init_creates_encryption_and_key_gen(self, mock_thread):
        from utils.av import AV
        mock_cls = MagicMock()

        av = AV(mock_cls)
        assert av.encryption is not None
        assert av.key_gen is not None
        assert av.key is not None

    @patch("utils.av._keygen_name", "DEBUG")
    @patch("utils.av.Thread")
    def test_init_starts_daemon_key_rotation_thread(self, mock_thread):
        from utils.av import AV
        mock_cls = MagicMock()

        _av = AV(mock_cls)
        mock_thread.assert_called_once()
        call_kwargs = mock_thread.call_args[1]
        assert call_kwargs["daemon"] is True
        mock_thread.return_value.start.assert_called_once()

    @patch("utils.av._keygen_name", "DEBUG")
    @patch("utils.av.Thread")
    def test_init_generates_namespaces(self, mock_thread):
        from utils.av import AV
        mock_cls = MagicMock()

        av = AV(mock_cls)
        assert av.client_namespaces is not None
        assert isinstance(av.client_namespaces, dict)


class TestGenerateNamespaces:
    def test_generate_flask_namespace_returns_dict(self):
        from utils.av import generate_flask_namespace
        mock_cls = MagicMock()
        result = generate_flask_namespace(mock_cls)
        assert isinstance(result, dict)
        assert "/video" in result
        assert "/audio" in result

    def test_generate_client_namespace_returns_dict(self):
        from utils.av import generate_client_namespace
        mock_cls = MagicMock()
        mock_av = MagicMock()
        result = generate_client_namespace(mock_cls, mock_av)
        assert isinstance(result, dict)
        assert "/video" in result
        assert "/audio" in result

    def test_testing_flag_switches_to_test_namespaces(self):
        import utils.av as av_mod
        orig = av_mod.testing
        try:
            av_mod.testing = True
            mock_cls = MagicMock()
            result = av_mod.generate_flask_namespace(mock_cls)
            assert "/test" in result
            assert "/video" not in result
        finally:
            av_mod.testing = orig
