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
    pass


class BadGateway(CustomException):
    code = 502
    message = "Bad Gateway"
    pass


class BadRequest(CustomException):
    code = 400
    message = "Bad Request"
    pass


class ParameterError(BadRequest):
    pass


class InvalidParameter(ParameterError):
    pass


class BadAuthentication(CustomException):
    code = 403
    message = "Forbidden"
    pass


class UserNotFound(BadAuthentication):
    pass


class UnexpectedResponse(CustomException):
    pass


class ConnectionRefused(UnexpectedResponse):
    pass


class InternalClientError(CustomException):
    pass


class UnknownError(CustomException):
    code = 0
    message = "Unknown Exception"
    pass


class Errors(Enum):
    # TODO: move error codes and messages into here
    BADREQUEST = BadRequest
    BADAUTHENTICATION = BadAuthentication
    SERVERERROR = ServerError
    BADGATEWAY = BadGateway
    PARAMETERERROR = ParameterError
    INVALIDPARAMETER = InvalidParameter
    USERNOTFOUND = UserNotFound
    UNEXPECTEDRESPONSE = UnexpectedResponse
    CONNECTIONREFUSED = ConnectionRefused
    INTERNALCLIENTERROR = InternalClientError
    UNKNOWNERROR = UnknownError

    def __call__(cls, message: str):
        return cls.value(message)
