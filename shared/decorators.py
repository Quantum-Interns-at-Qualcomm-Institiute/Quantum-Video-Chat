"""Shared decorators for Flask endpoint exception handling."""
import logging
from functools import wraps

from flask import jsonify

from shared.exceptions import (
    ServerError, BadRequest, BadGateway, BadAuthentication, InvalidState,
)

logger = logging.getLogger(__name__)


def _format_detail(exc: Exception) -> str:
    """Strip trailing period from exception message for JSON responses."""
    msg = str(exc)
    return msg.rstrip('.')


def handle_exceptions(endpoint_handler):
    """Decorator that catches common server exceptions and returns JSON errors.

    Works with both plain functions and classmethods that receive ``cls`` as
    their first argument.  For the ServerAPI pattern where ``cls`` is injected
    by the decorator itself, pass a *cls_provider* callable (see
    ``handle_exceptions_with_cls``).
    """
    @wraps(endpoint_handler)
    def wrapper(*args, **kwargs):
        try:
            return endpoint_handler(*args, **kwargs)
        except BadAuthentication as e:
            logger.info("Auth failed at %s: %s", endpoint_handler.__name__, e)
            return jsonify({"error_code": "403", "error_message": "Forbidden",
                            "details": _format_detail(e)}), 403
        except BadRequest as e:
            logger.info(str(e))
            return jsonify({"error_code": "400", "error_message": "Bad Request",
                            "details": _format_detail(e)}), 400
        except ServerError as e:
            logger.error(str(e))
            return jsonify({"error_code": "500", "error_message": "Internal Server Error",
                            "details": _format_detail(e)}), 500
        except InvalidState as e:
            logger.info(str(e))
            return jsonify({"error_code": "400", "error_message": "Bad Request",
                            "details": _format_detail(e)}), 400
        except BadGateway as e:
            logger.info(str(e))
            return jsonify({"error_code": "502", "error_message": "Bad Gateway",
                            "details": _format_detail(e)}), 502
    return wrapper


def handle_exceptions_with_cls(cls_provider):
    """Like ``handle_exceptions`` but injects *cls* (from *cls_provider*) as
    the first argument to the wrapped handler.

    Usage in ServerAPI::

        @app.route('/endpoint', methods=['POST'])
        @handle_exceptions_with_cls(lambda: ServerAPI)
        def my_endpoint(cls):
            ...
    """
    def decorator(endpoint_handler):
        @wraps(endpoint_handler)
        def wrapper(*args, **kwargs):
            cls = cls_provider()
            try:
                return endpoint_handler(cls, *args, **kwargs)
            except BadAuthentication as e:
                cls.logger.info("Auth failed at %s: %s", endpoint_handler.__name__, e)
                return jsonify({"error_code": "403", "error_message": "Forbidden",
                                "details": _format_detail(e)}), 403
            except BadRequest as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "400", "error_message": "Bad Request",
                                "details": _format_detail(e)}), 400
            except ServerError as e:
                cls.logger.error(str(e))
                return jsonify({"error_code": "500", "error_message": "Internal Server Error",
                                "details": _format_detail(e)}), 500
            except InvalidState as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "400", "error_message": "Bad Request",
                                "details": _format_detail(e)}), 400
            except BadGateway as e:
                cls.logger.info(str(e))
                return jsonify({"error_code": "502", "error_message": "Bad Gateway",
                                "details": _format_detail(e)}), 502
        return wrapper
    return decorator
