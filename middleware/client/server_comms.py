import time
import requests

from client.errors import Errors
from client.util import get_parameters, ClientState
from custom_logging import logger


class ServerCommsMixin:
    """
    Mixin providing server communication methods for Client.
    Assumes the host class has: server_endpoint, api_endpoint, state, user_id, connect_to_websocket()
    """

    def contact_server(self, route, json=None):
        endpoint = self.server_endpoint(route)
        logger.info(f"Contacting Server at {endpoint}.")
        try:
            response = requests.post(str(endpoint), json=json)
        except requests.exceptions.ConnectionError:
            raise Errors.CONNECTIONREFUSED.value(
                f"Unable to reach Server API at endpoint {endpoint}.")

        if response.status_code != 200:
            try:
                response.json()
            except requests.exceptions.JSONDecodeError:
                raise Errors.UNEXPECTEDRESPONSE.value(
                    f"Unexpected Server response at {endpoint}: {response.reason}.")
            context = response.json()['details'] if 'details' in response.json() else response.reason
            raise Errors.UNEXPECTEDRESPONSE.value(
                f"Unexpected Server response at {endpoint}: {context}.")
        return response

    def connect(self, max_retries=10, base_delay=2.0):
        """
        Attempt to connect to specified server with exponential backoff.
        Expects token and user_id in return.
        Return `True` iff successful.
        """
        logger.info(f"Attempting to connect to server: {self.server_endpoint}.")
        if self.state >= ClientState.LIVE:
            logger.error(f"Cannot connect to {self.server_endpoint}; already connected.")
            raise Errors.INTERNALCLIENTERROR.value(
                f"Cannot connect to {self.server_endpoint}; already connected.")

        for attempt in range(max_retries + 1):
            self.adapter.send_status('server_connecting', {
                'attempt': attempt + 1, 'max': max_retries + 1,
            })

            if attempt > 0:
                delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                logger.info(f"Retrying server connection in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{max_retries + 1})...")
                time.sleep(delay)

            try:
                response = self.contact_server('/create_user', json={
                    'api_endpoint': tuple(self.api_endpoint)
                })
            except Errors.CONNECTIONREFUSED.value as e:
                logger.warning(f"Connection attempt {attempt + 1}/{max_retries + 1} "
                               f"failed: {e}")
                if attempt == max_retries:
                    logger.error("All connection attempts exhausted.")
                    self.adapter.send_status('server_error', {
                        'reason': 'Max retries exceeded',
                    })
                    return False
                continue
            except Errors.UNEXPECTEDRESPONSE.value as e:
                logger.error(str(e))
                raise e

            try:
                (self.user_id,) = get_parameters(response.json(), 'user_id')
                logger.info(f"Received user_id '{self.user_id}'.")
            except Errors.PARAMETERERROR.value as e:
                context = f"Server response did not contain user_id at {self.server_endpoint('/create_user')}."
                logger.error(context)
                raise Errors.UNEXPECTEDRESPONSE.value(context)

            self.state = ClientState.LIVE
            self.adapter.send_status('server_connected', {'user_id': self.user_id})
            return True

        return False

    def connect_to_peer(self, peer_id):
        """
        Open Socket API. Contact Server /peer_connection and await connection from peer.
        The host's shared settings are included so the peer uses matching config.
        """
        from client.socket_client import SocketClient
        from shared.config import (
            VIDEO_SHAPE, FRAME_RATE, SAMPLE_RATE, AUDIO_WAIT,
            KEY_LENGTH, _scheme_name, _keygen_name,
        )

        logger.info(f"Attempting to initiate connection to peer User {peer_id}.")
        self.adapter.send_status('peer_outgoing', {'peer_id': peer_id})

        session_settings = {
            'video_width': VIDEO_SHAPE[1],
            'video_height': VIDEO_SHAPE[0],
            'frame_rate': FRAME_RATE,
            'sample_rate': SAMPLE_RATE,
            'audio_wait': AUDIO_WAIT,
            'key_length': KEY_LENGTH,
            'encrypt_scheme': _scheme_name,
            'key_generator': _keygen_name,
        }

        try:
            response = self.contact_server('/peer_connection', json={
                'user_id': self.user_id,
                'peer_id': peer_id,
                'session_settings': session_settings,
            })
        except Errors.CONNECTIONREFUSED.value as e:
            logger.error(str(e))
            raise e
        except Errors.UNEXPECTEDRESPONSE.value as e:
            logger.error(str(e))
            raise e

        (websocket_endpoint,) = get_parameters(response.json(), 'socket_endpoint')
        logger.info(f"Received websocket endpoint '{websocket_endpoint}'.")
        self.connect_to_websocket(websocket_endpoint)
        self.state = ClientState.CONNECTED
        self.adapter.send_status('peer_connected')

    def disconnect_from_server(self):
        """Notify the server that this client is leaving and reset state."""
        if self.state < ClientState.LIVE:
            return
        try:
            self.contact_server('/remove_user', json={'user_id': self.user_id})
        except Exception as e:
            logger.warning(f"Failed to notify server of disconnect: {e}")
        self.state = ClientState.INIT
