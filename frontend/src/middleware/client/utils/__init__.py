from enum import Enum
from functools import total_ordering


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


class UserNotFound(BadAuthentication):
    pass


def remove_last_period(string):
    string = str(string)
    if string[-1] == ".":
        return string[0:-1]
    return string


def get_parameters(data, *args):
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
    if isinstance(data, list) or isinstance(data, tuple):
        if len(args == 0):
            return get_parameters_from_sequence(data)
        return get_parameters_from_sequence(data, args[0])
    if data.isinstance(dict):
        return get_parameters_from_dict(data, *args)
    raise NotImplementedError


def get_parameters_from_sequence(data, validators=[]):
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
        raise ParameterError(
            f"Expected {len(validators)} parameters but received {len(data)}.")

    param_vals = ()
    for i in range(len(data)):
        param_val = data[i]
        validator = validators[i]
        if not validator:
            def validator(x): return True

        if not validator(param_val):
            raise InvalidParameter(f"Parameter {i+1} failed validation.")
        param_vals += (*param_vals, param_val)
    return param_vals


def get_parameters_from_dict(data, *args):
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
            validator = (lambda x: not not x)

        if param in data:
            param_val = data.get(param)
        else:
            raise ParameterError(f"Expected parameter '{param}' not received.")

        if not validator(param_val):
            raise InvalidParameter(f"Parameter '{param}' failed validation.")

        param_vals = (*param_vals, param_val)
    return param_vals


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
