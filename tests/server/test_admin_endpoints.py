"""Tests for admin endpoints in server/rest_api.py."""
import json
import os
import time
from collections import deque
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from shared.endpoint import Endpoint
from shared.exceptions import ServerError, BadRequest


class TestAdminEndpoints:
    """Test the /admin/* REST endpoints."""

    @pytest.fixture(autouse=True)
    def setup_api(self):
        from rest_api import ServerAPI
        from state import APIState
        from admin_routes import init_admin

        ServerAPI.state = APIState.INIT
        ServerAPI.server = MagicMock()
        ServerAPI.endpoint = Endpoint('127.0.0.1', 5050)
        ServerAPI.state = APIState.IDLE

        # Set up sensible defaults on the mock server
        ServerAPI.server.start_time = time.time() - 120  # 2 minutes ago
        ServerAPI.server.user_manager.get_all_users.return_value = {}
        ServerAPI.server.event_log = deque(maxlen=500)

        # Inject server into admin blueprint
        init_admin(ServerAPI.server, lambda: ServerAPI.state)

        self.api = ServerAPI
        self.client = ServerAPI.app.test_client()
        yield
        ServerAPI.state = APIState.INIT

    # ---- /admin/status ----

    def test_status_returns_uptime_and_config(self):
        self.api.server.user_manager.get_all_users.return_value = {
            'u1': {}, 'u2': {},
        }

        response = self.client.get('/admin/status')
        assert response.status_code == 200
        data = json.loads(response.data)

        assert 'uptime_seconds' in data
        assert data['uptime_seconds'] >= 120
        assert data['user_count'] == 2
        assert 'api_state' in data
        assert 'config' in data
        assert 'rest_port' in data['config']
        assert 'websocket_port' in data['config']
        assert 'local_ip' in data['config']

    # ---- /admin/users ----

    def test_users_returns_empty_dict(self):
        response = self.client.get('/admin/users')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['users'] == {}

    def test_users_returns_populated(self):
        self.api.server.user_manager.get_all_users.return_value = {
            'abc': {'api_endpoint': '127.0.0.1:4000', 'state': 'IDLE', 'peer': None},
        }

        response = self.client.get('/admin/users')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'abc' in data['users']
        assert data['users']['abc']['state'] == 'IDLE'

    # ---- /admin/events ----

    def test_events_returns_empty_list(self):
        response = self.client.get('/admin/events')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['events'] == []

    def test_events_returns_entries(self):
        self.api.server.event_log.append({
            'timestamp': '2026-01-01T00:00:00',
            'event': 'user_added',
            'user_id': 'u1',
        })
        self.api.server.event_log.append({
            'timestamp': '2026-01-01T00:00:01',
            'event': 'user_removed',
            'user_id': 'u1',
        })

        response = self.client.get('/admin/events')
        data = json.loads(response.data)
        assert len(data['events']) == 2

    def test_events_respects_limit(self):
        for i in range(10):
            self.api.server.event_log.append({
                'timestamp': f'2026-01-01T00:00:{i:02d}',
                'event': 'test',
            })

        response = self.client.get('/admin/events?limit=3')
        data = json.loads(response.data)
        assert len(data['events']) == 3

    # ---- /admin/logs ----

    def test_logs_missing_file_returns_empty(self):
        with patch('admin_routes.os.path.exists', return_value=False):
            response = self.client.get('/admin/logs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['lines'] == []
        assert 'file' in data

    def test_logs_reads_file(self, tmp_path):
        log_file = tmp_path / 'test.log'
        log_file.write_text('line1\nline2\nline3\n')

        import logging
        server_logger = logging.getLogger('server')
        server_logger.log_file_path = str(log_file)

        try:
            response = self.client.get('/admin/logs?lines=2')
        finally:
            del server_logger.log_file_path

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['lines']) == 2
        assert data['lines'][-1] == 'line3'

    # ---- /admin/disconnect/<user_id> ----

    def test_disconnect_success(self):
        response = self.client.post('/admin/disconnect/u1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'disconnected'
        assert data['user_id'] == 'u1'
        self.api.server.disconnect_peer.assert_called_once_with('u1')

    def test_disconnect_bad_request(self):
        self.api.server.disconnect_peer.side_effect = BadRequest("no such user")

        response = self.client.post('/admin/disconnect/u1')
        assert response.status_code == 400

    # ---- /admin/remove/<user_id> ----

    def test_remove_success(self):
        response = self.client.post('/admin/remove/u1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'removed'
        assert data['user_id'] == 'u1'
        self.api.server.remove_user.assert_called_once_with('u1')

    def test_remove_ignores_disconnect_failure(self):
        """Remove should still succeed even if disconnect_peer raises."""
        self.api.server.disconnect_peer.side_effect = Exception("peer gone")

        response = self.client.post('/admin/remove/u1')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'removed'

    # ---- CORS ----

    def test_cors_headers_present(self):
        response = self.client.get('/admin/status')
        assert response.headers.get('Access-Control-Allow-Origin') == '*'
        assert 'GET' in response.headers.get('Access-Control-Allow-Methods', '')
