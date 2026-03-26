"""Parameter extraction and validation utilities."""

from shared.exceptions import InvalidParameter, ParameterError


def _default_validator(x):
    """Default validator: truthy check."""
    return bool(x)


def get_parameters(data: list | tuple | dict, *args: list | str | tuple | None):  # noqa: C901 -- parameter dispatch is inherently branchy
    """Return desired parameters from a collection with optional validation.

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
    def get_from_iterable(items, validators):
        if len(validators) == 0:
            return (*items,)
        if len(items) != len(validators):
            msg = f"Expected {len(validators)} parameters but received {len(items)}."
            raise ParameterError(msg)

        param_vals = ()
        for param, check_fn in zip(items, validators, strict=False):
            effective_validator = check_fn or _default_validator
            if not effective_validator(param):
                msg = "Parameter failed validation."
                raise InvalidParameter(msg)
            param_vals = (*param_vals, param)
        return param_vals

    def get_from_dict(mapping, *keys):
        param_vals = ()
        for key in keys:
            if isinstance(key, tuple):
                param, validator = key
            else:
                param = key
                validator = _default_validator

            if param not in mapping:
                msg = f"Expected parameter '{param}' not received."
                raise ParameterError(msg)

            param_val = mapping.get(param)
            if not validator(param_val):
                msg = f"Parameter '{param}' failed validation."
                raise InvalidParameter(msg)

            param_vals = (*param_vals, param_val)
        return param_vals

    if isinstance(data, (list, tuple)):
        return get_from_iterable(
            data,
            args[0] if len(args) == 1 and isinstance(args[0], (list, tuple)) else args,
        )
    if isinstance(data, dict):
        return get_from_dict(data, *args)
    msg = f"Unsupported data type: {type(data)}"
    raise NotImplementedError(msg)


def is_type(type_):
    """Return a validator that checks isinstance against the given type."""
    def _check(x):
        return isinstance(x, type_)
    return _check
