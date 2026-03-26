"""ClientNotifier -- Sends HTTP notifications to client middleware APIs.

Single responsibility: outbound REST communication to client endpoints.
"""
import requests
from custom_logging import logger


class ClientNotifier:
    """Sends REST notifications to client middleware APIs."""

    def __init__(self, server):
        """Initialize with a server that provides user lookups.

        Parameters
        ----------
        server : object
            Any object with a ``get_user(user_id)`` method returning a User
            that has an ``api_endpoint(route)`` method.
        """
        self._server = server

    def notify(self, user_id, route, json):
        """POST a JSON payload to a client's API endpoint.

        Returns the ``requests.Response`` object.
        Raises on connection failure so callers can handle errors.
        """
        endpoint = self._server.get_user(user_id).api_endpoint(route)
        logger.info("Contacting Client API for User %s at %s.", user_id, endpoint)
        try:
            # 8-second timeout: middleware /peer_connection returns immediately
            # (WebSocket connect runs in a background greenlet), so this should
            # normally complete in milliseconds.
            from shared.ssl_utils import get_ssl_context  # noqa: PLC0415
            # Self-signed certs are expected for internal server-to-middleware calls
            verify = not get_ssl_context()
            response = requests.post(str(endpoint), json=json, timeout=8, verify=verify)
        except requests.RequestException:
            logger.error(
                "Unable to reach Client API for User %s at endpoint %s.", user_id, endpoint)
            raise
        return response
