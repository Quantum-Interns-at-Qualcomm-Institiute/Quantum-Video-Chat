"""Custom exception hierarchy for server error handling."""

from enum import Enum

from flask import jsonify


class CustomExceptionError(Exception):
    """Base exception with HTTP status code and message."""

    code = -1
    message = ""

    def info(self, details: str):
        """Return a JSON error response tuple."""
        return jsonify({"error_code": self.code,
                        "error_message": self.message,
                        "details": details,
                        }), self.code


# Keep old name as alias for backward compatibility
CustomException = CustomExceptionError


class ServerError(CustomExceptionError):
    """Internal server error (500)."""

    code = 500
    message = "Internal Server Error"


class BadGatewayError(CustomExceptionError):
    """Bad gateway error (502)."""

    code = 502
    message = "Bad Gateway"


# Keep old name as alias for backward compatibility
BadGateway = BadGatewayError


class BadRequestError(CustomExceptionError):
    """Bad request error (400)."""

    code = 400
    message = "Bad Request"


# Keep old name as alias for backward compatibility
BadRequest = BadRequestError


class ParameterError(BadRequest):
    """Raised when required parameters are missing."""


class InvalidParameterError(ParameterError):
    """Raised when a parameter fails validation."""


# Keep old name as alias for backward compatibility
InvalidParameter = InvalidParameterError


class BadAuthenticationError(CustomExceptionError):
    """Authentication failure (403)."""

    code = 403
    message = "Forbidden"


# Keep old name as alias for backward compatibility
BadAuthentication = BadAuthenticationError


class UserNotFound(BadAuthentication):
    """Raised when a requested user does not exist."""


class UnexpectedResponseError(CustomExceptionError):
    """Raised on unexpected response from a remote service."""


# Keep old name as alias for backward compatibility
UnexpectedResponse = UnexpectedResponseError


class ConnectionRefused(UnexpectedResponse):
    """Raised when a connection to a remote service is refused."""


class InternalClientError(CustomExceptionError):
    """Raised on internal client-side errors."""


class InvalidStateError(Exception):
    """Raised when an operation is attempted in an invalid state."""


# Keep old name as alias for backward compatibility
InvalidState = InvalidStateError


class UnknownError(CustomExceptionError):
    """Unknown or unclassified error."""

    code = 0
    message = "Unknown Exception"


class Errors(Enum):
    """Registry of all error types for programmatic lookup."""

    BADREQUEST = BadRequest
    BADAUTHENTICATION = BadAuthentication
    SERVERERROR = ServerError
    BADGATEWAY = BadGateway
    PARAMETERERROR = ParameterError
    INVALIDPARAMETER = InvalidParameterError
    INVALIDSTATE = InvalidStateError
    USERNOTFOUND = UserNotFound
    UNEXPECTEDRESPONSE = UnexpectedResponse
    CONNECTIONREFUSED = ConnectionRefused
    INTERNALCLIENTERROR = InternalClientError
    UNKNOWNERROR = UnknownError
