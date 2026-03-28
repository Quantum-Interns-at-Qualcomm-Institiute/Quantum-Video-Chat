"""Admin dashboard and monitoring endpoints -- separated from user-facing API."""
import ipaddress
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

from shared.config import LOCAL_IP, SERVER_REST_PORT
from shared.decorators import handle_exceptions

admin_bp = Blueprint("admin", __name__)

from shared.logging import get_logger
logger = get_logger(__name__)

_ADMIN_KEY = os.environ.get("QVC_ADMIN_KEY", "")


def _check_admin_auth(req):
    """Return True if the request is authorized for admin access."""
    if _ADMIN_KEY:
        auth = req.headers.get("Authorization", "")
        ok = auth == f"Bearer {_ADMIN_KEY}"
        if not ok:
            logger.warning("Admin auth failed from %s", req.remote_addr)
        return ok
    # No key configured — allow loopback and private (Docker bridge) networks.
    addr = ipaddress.ip_address(req.remote_addr)
    allowed = addr.is_loopback or addr.is_private
    if not allowed:
        logger.warning("Admin access denied for non-private IP %s", addr)
    return allowed

# Reference to the Server instance — set by ServerAPI when registering the blueprint.
_server = None
_get_state = None
_shutdown_fn = None


def init_admin(server, get_state, shutdown_fn=None):
    """Called by ServerAPI to inject the server instance, state accessor, and shutdown hook."""
    global _server, _get_state, _shutdown_fn  # noqa: PLW0603 -- module-level singletons set once at init
    _server = server
    _get_state = get_state
    _shutdown_fn = shutdown_fn
    logger.debug("Admin routes initialized  shutdown_fn=%s", shutdown_fn is not None)


# region --- Dashboard ---

@admin_bp.route("/dashboard")
def dashboard():
    """Serve the admin dashboard web UI."""
    logger.debug("GET /dashboard from %s", request.remote_addr)
    return render_template("dashboard.html")

# endregion

# region --- Health Check ---

@admin_bp.route("/health", methods=["GET"])
def health_check():
    """Liveness probe — returns 200 if the server process is running."""
    uptime = time.time() - _server.start_time if _server else 0
    state_val = _get_state().value if _get_state else "unknown"
    logger.debug("GET /health  uptime=%.1f  state=%s", uptime, state_val)
    return jsonify({
        "status": "healthy",
        "uptime_seconds": round(uptime, 1),
        "api_state": state_val,
    }), 200

# endregion

# region --- Admin Endpoints ---

@admin_bp.route("/admin/status", methods=["GET"])
@handle_exceptions
def admin_status():
    """Return server uptime, state, user count, and configuration."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    logger.debug("GET /admin/status from %s", request.remote_addr)
    uptime = time.time() - _server.start_time
    all_users = _server.user_manager.get_all_users()
    user_count = len(all_users)
    # Count only users whose state is CONNECTED (i.e. actively in a call).
    # get_all_users() returns serialized dicts with state as a string value.
    # Each call has 2 CONNECTED users, so call_count = connected_users / 2.
    connected_count = sum(
        1 for u in all_users.values() if u.get("state") == "CONNECTED"
    )
    call_count = connected_count // 2
    return jsonify({
        "uptime_seconds": round(uptime, 1),
        "api_state": _get_state().value,
        "user_count": user_count,
        "call_count": call_count,
        "config": {
            "rest_port": SERVER_REST_PORT,
            "local_ip": LOCAL_IP,
        },
    }), 200


@admin_bp.route("/admin/users", methods=["GET"])
@handle_exceptions
def admin_users():
    """Return all connected users with their states and peers."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    users = _server.user_manager.get_all_users()
    logger.debug("GET /admin/users -> %d user(s)", len(users))
    return jsonify({"users": users}), 200


@admin_bp.route("/admin/events", methods=["GET"])
@handle_exceptions
def admin_events():
    """Return recent server events (connection history)."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    limit = request.args.get("limit", 50, type=int)
    events = list(_server.event_log)[-limit:]
    return jsonify({"events": events}), 200


@admin_bp.route("/admin/logs", methods=["GET"])
@handle_exceptions
def admin_logs():
    """Return recent lines from the server log file for this run."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    lines_count = request.args.get("lines", 100, type=int)
    # Resolve the log file from the logger so we always read the file
    # created at startup — not a date-derived guess that breaks per-run files.
    server_logger = logging.getLogger("server")
    log_path = getattr(server_logger, "log_file_path", None)
    if not log_path or not Path(log_path).exists():
        return jsonify({"lines": [], "file": log_path or ""}), 200
    with Path(log_path).open() as f:
        all_lines = deque(f, maxlen=lines_count)
    return jsonify({
        "lines": [line.rstrip("\n") for line in all_lines],
        "file": Path(log_path).name,
    }), 200


@admin_bp.route("/admin/disconnect/<user_id>", methods=["POST"])
@handle_exceptions
def admin_disconnect(user_id):
    """Force-disconnect a user from their peer."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    logger.info("POST /admin/disconnect/%s", user_id)
    _server.disconnect_peer(user_id)
    logger.debug("POST /admin/disconnect/%s -> done", user_id)
    return jsonify({"status": "disconnected", "user_id": user_id}), 200


@admin_bp.route("/admin/remove/<user_id>", methods=["POST"])
@handle_exceptions
def admin_remove(user_id):
    """Force-disconnect and remove a user from the server."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    logger.info("POST /admin/remove/%s", user_id)
    try:
        _server.disconnect_peer(user_id)
    except Exception:  # noqa: BLE001 -- best-effort disconnect before removal
        logger.debug("User %s may not have a peer (ok)", user_id)
    _server.remove_user(user_id)
    logger.debug("POST /admin/remove/%s -> done", user_id)
    return jsonify({"status": "removed", "user_id": user_id}), 200


@admin_bp.route("/admin/shutdown", methods=["POST"])
@handle_exceptions
def admin_shutdown():
    """Gracefully shut down the entire server."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    if _shutdown_fn is None:
        logger.warning("POST /admin/shutdown -- shutdown_fn not configured")
        return jsonify({"error": "Shutdown not available"}), 503

    logger.info("POST /admin/shutdown -- initiating graceful shutdown in 0.5s")
    threading.Timer(0.5, _shutdown_fn).start()
    return jsonify({"status": "shutting_down"}), 200

# endregion


# region --- Quantum / BB84 Endpoints ---

@admin_bp.route("/admin/quantum/metrics", methods=["GET"])
@handle_exceptions
def admin_quantum_metrics():
    """Return current BB84/QBER metrics if BB84 mode is active."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    if _server is None or not hasattr(_server, "qber_monitor") or _server.qber_monitor is None:
        return jsonify({"bb84_active": False}), 200

    monitor = _server.qber_monitor
    summary = monitor.get_summary()
    history = [s.to_dict() for s in monitor.get_history()]
    return jsonify({
        "bb84_active": True,
        "summary": summary,
        "history": history,
    }), 200


@admin_bp.route("/admin/quantum/config", methods=["GET"])
@handle_exceptions
def admin_quantum_config():
    """Return current BB84 configuration."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    from shared.config import _default  # noqa: PLC0415
    return jsonify({
        "key_generator": _default.key_generator,
        "bb84_num_raw_bits": _default.bb84_num_raw_bits,
        "bb84_qber_threshold": _default.bb84_qber_threshold,
        "bb84_fiber_length_km": _default.bb84_fiber_length_km,
        "bb84_source_intensity": _default.bb84_source_intensity,
        "bb84_detector_efficiency": _default.bb84_detector_efficiency,
        "bb84_eavesdropper_enabled": _default.bb84_eavesdropper_enabled,
    }), 200


@admin_bp.route("/admin/quantum/eavesdropper", methods=["POST"])
@handle_exceptions
def admin_toggle_eavesdropper():
    """Toggle eavesdropper simulation for demo purposes."""
    if not _check_admin_auth(request):
        return jsonify({"error": "Forbidden"}), 403
    if _server is None or not hasattr(_server, "bb84_key_gen") or _server.bb84_key_gen is None:
        return jsonify({"error": "BB84 mode not active"}), 400

    from shared.bb84.protocol import EavesdropperSimulator  # noqa: PLC0415
    key_gen = _server.bb84_key_gen

    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled", key_gen._eavesdropper is None)  # noqa: SLF001 -- admin endpoint needs internal state
    rate = data.get("interception_rate", 1.0)

    if enabled:
        key_gen.set_eavesdropper(EavesdropperSimulator(interception_rate=rate))
        status = "enabled"
    else:
        key_gen.clear_eavesdropper()
        status = "disabled"

    logger.info("Eavesdropper simulation %s (rate=%.2f)", status, rate)
    return jsonify({"eavesdropper": status, "interception_rate": rate}), 200

# endregion
