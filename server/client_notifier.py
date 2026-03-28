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
        logger.debug("ClientNotifier initialized")

    def notify(self, user_id, route, json):
        """POST a JSON payload to a client's API endpoint.

        Returns the ``requests.Response`` object.
        Raises on connection failure so callers can handle errors.
        """
        endpoint = self._server.get_user(user_id).api_endpoint(route)
        logger.info("Notifying user %s: POST %s", user_id, endpoint)
        logger.debug("Notify payload: %s", json)
        try:
            from shared.ssl_utils import get_ssl_context  # noqa: PLC0415
            verify = not get_ssl_context()
            response = requests.post(str(endpoint), json=json, timeout=8, verify=verify)
            logger.debug("Notify response: %s %s", response.status_code, response.reason)
        except requests.RequestException:
            logger.error(
                "Unable to reach Client API for User %s at endpoint %s.", user_id, endpoint)
            raise
        return response
