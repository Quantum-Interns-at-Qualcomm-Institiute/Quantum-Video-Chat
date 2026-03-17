# Re-export shared types so existing server imports continue to work.
from shared.endpoint import Endpoint
from shared.state import ClientState
from shared.exceptions import (
    ServerError, BadGateway, BadRequest,
    ParameterError, InvalidParameter,
    BadAuthentication, UserNotFound,
    Errors,
)
from shared.parameters import get_parameters, is_type
from shared.config import get_local_ip


def remove_last_period(string):
    string = str(string)
    if string[-1] == ".":
        return string[0:-1]
    return string
