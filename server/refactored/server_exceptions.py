from enum import Enum


class ServerError(Exception):
    pass


class BadGateway(Exception):
    pass


class BadRequest(Exception):
    pass


class ParameterError(BadRequest):
    pass


class InvalidParameter(ParameterError):
    pass


class BadAuthentication(Exception):
    pass


class DuplicateUser(Exception):
    pass


class UserNotFound(Exception):
    pass


class InvalidState(Exception):
    pass


class IdentityMismatch(Exception):
    pass


class ServerExceptions(Enum):
    SERVER_ERROR = ServerError
    BAD_GATEWAY = BadGateway
    BAD_REQUEST = BadRequest
    PARAMETER_ERROR = ParameterError
    INVALID_PARAMETER = InvalidParameter
    BAD_AUTHENTICATION = BadAuthentication
    DUPLICATE_USER = DuplicateUser
    USER_NOT_FOUND = UserNotFound
    INVALID_STATE = InvalidState
    IDENTITY_MISMATCH = IdentityMismatch

    def __call__(cls, message: str):
        return cls.value(message)
    # TODO: Flesh out
