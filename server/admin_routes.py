"""Admin dashboard and monitoring endpoints — separated from user-facing API."""
import logging
import os
import threading
import time
from collections import deque

from flask import Blueprint, jsonify, request, render_template

from shared.config import SERVER_REST_PORT, SERVER_WEBSOCKET_PORT, LOCAL_IP
from shared.decorators import handle_exceptions

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger('ServerAPI')

# Reference to the Server instance — set by ServerAPI when registering the blueprint.
_server = None
_get_state = None
_shutdown_fn = None


def init_admin(server, get_state, shutdown_fn=None):
    """Called by ServerAPI to inject the server instance, state accessor, and shutdown hook."""
    global _server, _get_state, _shutdown_fn
    _server = server
    _get_state = get_state
    _shutdown_fn = shutdown_fn


# region --- Dashboard ---

@admin_bp.route('/dashboard')
def dashboard():
    """Serve the admin dashboard web UI."""
    return render_template('dashboard.html')

# endregion

# region --- Admin Endpoints ---

@admin_bp.route('/admin/status', methods=['GET'])
@handle_exceptions
def admin_status():
    """Return server uptime, state, user count, and configuration."""
    uptime = time.time() - _server.start_time
    all_users = _server.user_manager.get_all_users()
    user_count = len(all_users)
    # Count only users whose state is CONNECTED (i.e. actively in a call).
    # get_all_users() returns serialized dicts with state as a string value.
    # Each call has 2 CONNECTED users, so call_count = connected_users / 2.
    connected_count = sum(
        1 for u in all_users.values() if u.get('state') == 'CONNECTED'
    )
    call_count = connected_count // 2
    return jsonify({
        'uptime_seconds': round(uptime, 1),
        'api_state': _get_state().value,
        'user_count': user_count,
        'call_count': call_count,
        'config': {
            'rest_port': SERVER_REST_PORT,
            'websocket_port': SERVER_WEBSOCKET_PORT,
            'local_ip': LOCAL_IP,
        },
    }), 200


@admin_bp.route('/admin/users', methods=['GET'])
@handle_exceptions
def admin_users():
    """Return all connected users with their states and peers."""
    users = _server.user_manager.get_all_users()
    return jsonify({'users': users}), 200


@admin_bp.route('/admin/events', methods=['GET'])
@handle_exceptions
def admin_events():
    """Return recent server events (connection history)."""
    limit = request.args.get('limit', 50, type=int)
    events = list(_server.event_log)[-limit:]
    return jsonify({'events': events}), 200


@admin_bp.route('/admin/logs', methods=['GET'])
@handle_exceptions
def admin_logs():
    """Return recent lines from the server log file for this run."""
    lines_count = request.args.get('lines', 100, type=int)
    # Resolve the log file from the logger so we always read the file
    # created at startup — not a date-derived guess that breaks per-run files.
    server_logger = logging.getLogger('server')
    log_path = getattr(server_logger, 'log_file_path', None)
    if not log_path or not os.path.exists(log_path):
        return jsonify({'lines': [], 'file': log_path or ''}), 200
    with open(log_path, 'r') as f:
        all_lines = deque(f, maxlen=lines_count)
    return jsonify({
        'lines': [line.rstrip('\n') for line in all_lines],
        'file': os.path.basename(log_path),
    }), 200


@admin_bp.route('/admin/disconnect/<user_id>', methods=['POST'])
@handle_exceptions
def admin_disconnect(user_id):
    """Force-disconnect a user from their peer."""
    _server.disconnect_peer(user_id)
    return jsonify({'status': 'disconnected', 'user_id': user_id}), 200


@admin_bp.route('/admin/remove/<user_id>', methods=['POST'])
@handle_exceptions
def admin_remove(user_id):
    """Force-disconnect and remove a user from the server."""
    try:
        _server.disconnect_peer(user_id)
    except Exception:
        pass  # User may not have a peer
    _server.remove_user(user_id)
    return jsonify({'status': 'removed', 'user_id': user_id}), 200


@admin_bp.route('/admin/shutdown', methods=['POST'])
@handle_exceptions
def admin_shutdown():
    """Gracefully shut down the entire server."""
    if _shutdown_fn is None:
        return jsonify({'error': 'Shutdown not available'}), 503

    # Return the response first, then shut down on a background thread
    # so the HTTP response actually reaches the client.
    threading.Timer(0.5, _shutdown_fn).start()
    return jsonify({'status': 'shutting_down'}), 200

# endregion
