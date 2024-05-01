from enum import Enum
from functools import total_ordering
from typing import Callable, Union

from flask import jsonify


@total_ordering
class ClientState(Enum):
    NEW = 'NEW'  # Uninitialized
    INIT = 'INIT'  # Initialized
    LIVE = 'LIVE'  # Connected to server
    CONNECTED = 'CONNECTED'  # Connected to peer

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented


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


def get_parameters(data: Union[list, tuple, dict], *args: Union[list, str, tuple[str, Callable], None]):
    """
    Returns desired parameters from a collection with optional data validation.
    Validator functions return true iff associated data is valid.

    Parameters
    ----------
    data : list, tuple, dict
    arg : list, optional
        If `data` is a sequence, list of validator functions (or `None`).
    arg : str, optional
        If `data` is a dict, key of desired data.
    arg : tuple(str, func), optional
        If `data` is a dict
    """
    def get_from_iterable(data: Union[list, tuple], validators: Union[list, tuple, None]):
        """
        Returns desired data from a list or or tuple with optional data validation.
        Validator functions return true iff associated data is valid.

        Parameters
        ----------
        data : list, tuple
        validators : list, tuple, optional
            Contains validator functions (or `None`) which return true iff
            associated data is acceptable. Must match order and length of `data`.
        """
        if len(validators) == 0:
            return (*data,)
        if len(data) != len(validators):
            raise Errors.PARAMETERERROR.value(
                f"Expected {len(validators)} parameters but received {len(data)}.")

        param_vals = ()
        for param, validator in zip(data, validators):
            if not validator:
                validator = lambda x: not not x

            if not validator(param):
                raise InvalidParameter("Parameter failed validation.")
            param_vals += (*param_vals, param)
        return param_vals

    def get_from_dict(data: dict, *args: Union[str, tuple[str, callable], None]):
        """
        Returns desired data from a dict with optional data validation.
        Validator functions return true iff associated data is valid.

        Parameters
        ----------
        data : dict
        arg : str, optional
            Key of desired data
        arg : tuple(str, func), optional
        """
        param_vals = ()
        for arg in args:
            if isinstance(arg, tuple):
                param, validator = arg
            else:
                param = arg
                # Truthy/Falsy coersion to bool
                validator = lambda x: not not x

            if param in data:
                param_val = data.get(param)
            else:
                raise Errors.PARAMETERERROR.value(f"Expected parameter '{
                                            param}' not received.")

            if not validator(param_val):
                raise InvalidParameter(
                    f"Parameter '{param}' failed validation.")

            param_vals = (*param_vals, param_val)
        return param_vals

    if isinstance(data, list) or isinstance(data, tuple):
        return get_from_iterable(data, args if len(args == 0) else args[0])
    if isinstance(data, dict):
        return get_from_dict(data, *args)


class Endpoint:
    def __init__(self, ip: str, port: int, route: str = None):
        if not ip:
            self.ip = None
        elif ip.startswith('https://'):
            self.ip = ip[8:]
        elif ip.startswith('http://'):
            self.ip = ip[7:]
        else:
            self.ip = ip

        self.port = port

        if not route:
            self.route = None
        elif route == '/':
            self.route = None
        elif route.startswith('/'):
            self.route = route[1:]
        else:
            self.route = route

    def __call__(self, route: str):
        if not route:
            return self
        endpoint = Endpoint(*self)
        endpoint.route = route
        return Endpoint(*endpoint)  # Re-instantiating fixes slashes in `route`

    def to_string(self):
        ip = self.ip if self.ip else 'localhost'
        port = f":{self.port}" if self.port else ''
        route = f"/{self.route}" if self.route else ''
        return f"http://{ip}{port}{route}"

    def __str__(self):
        return self.to_string()

    def __repr__(self):
        return self.to_string()

    def __unicode__(self):
        return self.to_string()

    def __iter__(self):
        yield self.ip if self.ip else 'localhost'
        if self.port:
            yield self.port
        if self.route:
            yield self.route
