from enum import Enum
from functools import total_ordering
from typing import Callable, Union
from client.errors import Errors


@total_ordering
class ClientState(Enum):
    NEW = 'NEW'  # Uninitialized
    INITIALIZED = 'INITIALIZED'  # Initialized
    CONNECTING = 'CONNECTING'
    LIVE = 'LIVE'  # Connected to server
    CONNECTED = 'CONNECTED'  # Connected to peer

    def __lt__(cls, other):
        if cls.__class__ is other.__class__:
            arr = list(cls.__class__)
            return arr.index(cls) < arr.index(other)
        return NotImplemented


@total_ordering
class APIState(Enum):
    NEW = 'NEW'
    INITIALIZED = 'INITIALIZED'
    LIVE = 'LIVE'

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            arr = list(self.__class__)
            return arr.index(self) < arr.index(other)
        return NotImplemented


def remove_last_period(text: str):
    return text[0:-1] if text[-1] == "." else text


def display_message(user_id, msg):
    print(f"({user_id}): {msg}")


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
            raise Errors.PARAMETERERROR(
                f"Expected {len(validators)} parameters but received {len(data)}.")

        param_vals = ()
        for param, validator in zip(data, validators):
            if not validator:
                validator = lambda x: not not x

            if not validator(param):
                raise Errors.INVALIDPARAMETER(
                    "Parameter failed validation.")
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
                raise Errors.PARAMETERERROR(f"Expected parameter '{param}' not received.")

            if not validator(param_val):
                raise Errors.INVALIDPARAMETER(
                    f"Parameter '{param}' failed validation.")

            param_vals = (*param_vals, param_val)
        return param_vals

    if isinstance(data, list) or isinstance(data, tuple):
        return get_from_iterable(data, args if len(args == 0) else args[0])
    if isinstance(data, dict):
        return get_from_dict(data, *args)
