"""Tests for shared/exceptions.py — exception hierarchy and Errors enum."""
import pytest
from flask import Flask

from shared.exceptions import (
    BadAuthentication,
    BadGateway,
    BadRequest,
    ConnectionRefused,
    CustomException,
    Errors,
    InternalClientError,
    InvalidParameter,
    ParameterError,
    ServerError,
    UnexpectedResponse,
    UnknownError,
    UserNotFound,
)


class TestHTTPCodes:
    def test_server_error(self):
        assert ServerError.code == 500

    def test_bad_gateway(self):
        assert BadGateway.code == 502

    def test_bad_request(self):
        assert BadRequest.code == 400

    def test_bad_authentication(self):
        assert BadAuthentication.code == 403

    def test_unknown_error(self):
        assert UnknownError.code == 0


class TestInheritance:
    def test_parameter_error_is_bad_request(self):
        assert issubclass(ParameterError, BadRequest)

    def test_invalid_parameter_is_parameter_error(self):
        assert issubclass(InvalidParameter, ParameterError)

    def test_user_not_found_is_bad_authentication(self):
        assert issubclass(UserNotFound, BadAuthentication)

    def test_connection_refused_is_unexpected_response(self):
        assert issubclass(ConnectionRefused, UnexpectedResponse)

    def test_all_inherit_from_custom_exception(self):
        for cls in [ServerError, BadGateway, BadRequest, BadAuthentication,
                    InternalClientError, UnknownError, UnexpectedResponse]:
            assert issubclass(cls, CustomException)


class TestInfoMethod:
    @pytest.fixture
    def app(self):
        app = Flask(__name__)
        return app

    def test_info_returns_tuple(self, app):
        with app.app_context():
            response, code = BadRequest().info("test details")
            assert code == 400

    def test_info_json_structure(self, app):
        with app.app_context():
            response, code = ServerError().info("something broke")
            data = response.get_json()
            assert data['error_code'] == 500
            assert data['error_message'] == 'Internal Server Error'
            assert data['details'] == 'something broke'


class TestErrorsEnum:
    def test_bad_request(self):
        assert Errors.BADREQUEST.value is BadRequest

    def test_server_error(self):
        assert Errors.SERVERERROR.value is ServerError

    def test_bad_gateway(self):
        assert Errors.BADGATEWAY.value is BadGateway

    def test_user_not_found(self):
        assert Errors.USERNOTFOUND.value is UserNotFound

    def test_connection_refused(self):
        assert Errors.CONNECTIONREFUSED.value is ConnectionRefused

    def test_internal_client_error(self):
        assert Errors.INTERNALCLIENTERROR.value is InternalClientError

    def test_all_members(self):
        assert len(Errors) == 12
