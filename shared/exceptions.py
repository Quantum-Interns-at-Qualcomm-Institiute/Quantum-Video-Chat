from enum import Enum
from flask import jsonify


class CustomException(Exception):
    code = -1
    message = ""

    def info(cls, details: str):
        return jsonify({"error_code": cls.code,
                        "error_message": cls.message,
                        "details": details
                        }), cls.code


class ServerError(CustomException):
    code = 500
    message = "Internal Server Error"


class BadGateway(CustomException):
    code = 502
    message = "Bad Gateway"


class BadRequest(CustomException):
    code = 400
    message = "Bad Request"


class ParameterError(BadRequest):
    pass


class InvalidParameter(ParameterError):
    pass


class BadAuthentication(CustomException):
    code = 403
    message = "Forbidden"


class UserNotFound(BadAuthentication):
    pass


class UnexpectedResponse(CustomException):
    pass


class ConnectionRefused(UnexpectedResponse):
    pass


class InternalClientError(CustomException):
    pass


class InvalidState(Exception):
    """Raised when an operation is attempted in an invalid state."""
    pass


class UnknownError(CustomException):
    code = 0
    message = "Unknown Exception"


class Errors(Enum):
    BADREQUEST = BadRequest
    BADAUTHENTICATION = BadAuthentication
    SERVERERROR = ServerError
    BADGATEWAY = BadGateway
    PARAMETERERROR = ParameterError
    INVALIDPARAMETER = InvalidParameter
    INVALIDSTATE = InvalidState
    USERNOTFOUND = UserNotFound
    UNEXPECTEDRESPONSE = UnexpectedResponse
    CONNECTIONREFUSED = ConnectionRefused
    INTERNALCLIENTERROR = InternalClientError
    UNKNOWNERROR = UnknownError
