from shared.exceptions import InvalidParameter, ParameterError


def get_parameters(data: list | tuple | dict, *args: list | str | tuple | None):
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
        If `data` is a dict, key + validator function pair.
    """
    def get_from_iterable(data, validators):
        if len(validators) == 0:
            return (*data,)
        if len(data) != len(validators):
            raise ParameterError(
                f"Expected {len(validators)} parameters but received {len(data)}.")

        param_vals = ()
        for param, validator in zip(data, validators):
            if not validator:
                validator = lambda x: bool(x)
            if not validator(param):
                raise InvalidParameter("Parameter failed validation.")
            param_vals = (*param_vals, param)
        return param_vals

    def get_from_dict(data, *args):
        param_vals = ()
        for arg in args:
            if isinstance(arg, tuple):
                param, validator = arg
            else:
                param = arg
                validator = lambda x: bool(x)

            if param not in data:
                raise ParameterError(
                    f"Expected parameter '{param}' not received.")

            param_val = data.get(param)
            if not validator(param_val):
                raise InvalidParameter(
                    f"Parameter '{param}' failed validation.")

            param_vals = (*param_vals, param_val)
        return param_vals

    if isinstance(data, (list, tuple)):
        return get_from_iterable(data, args[0] if len(args) == 1 and isinstance(args[0], (list, tuple)) else args)
    if isinstance(data, dict):
        return get_from_dict(data, *args)
    raise NotImplementedError(f"Unsupported data type: {type(data)}")


def is_type(type_):
    return lambda x: isinstance(x, type_)
