"""Tests for shared/endpoint.py — Endpoint class."""
import pytest
from unittest.mock import patch
from shared.endpoint import Endpoint


class TestEndpointConstructor:
    def test_bare_ip(self):
        ep = Endpoint('192.168.1.1', 8080)
        assert ep.ip == '192.168.1.1'
        assert ep.port == 8080

    def test_strips_http(self):
        ep = Endpoint('http://192.168.1.1', 8080)
        assert ep.ip == '192.168.1.1'

    def test_strips_https(self):
        ep = Endpoint('https://10.0.0.1', 443)
        assert ep.ip == '10.0.0.1'

    def test_none_ip(self):
        ep = Endpoint(None, 5000)
        assert ep.ip is None

    def test_empty_string_ip(self):
        ep = Endpoint('', 5000)
        assert ep.ip is None

    def test_route_strips_leading_slash(self):
        ep = Endpoint('1.2.3.4', 80, '/api')
        assert ep.route == 'api'

    def test_route_bare_slash_becomes_none(self):
        ep = Endpoint('1.2.3.4', 80, '/')
        assert ep.route is None

    def test_route_none(self):
        ep = Endpoint('1.2.3.4', 80, None)
        assert ep.route is None

    def test_route_empty_string(self):
        ep = Endpoint('1.2.3.4', 80, '')
        assert ep.route is None

    def test_route_no_leading_slash(self):
        ep = Endpoint('1.2.3.4', 80, 'api/v1')
        assert ep.route == 'api/v1'


@patch('shared.ssl_utils.get_ssl_context', return_value=None)
class TestEndpointToString:
    def test_full(self, _mock_ssl):
        ep = Endpoint('1.2.3.4', 80, 'api')
        assert ep.to_string() == 'http://1.2.3.4:80/api'

    def test_none_ip_falls_back_to_localhost(self, _mock_ssl):
        ep = Endpoint(None, 5000)
        assert ep.to_string() == 'http://localhost:5000'

    def test_none_port_omitted(self, _mock_ssl):
        ep = Endpoint('1.2.3.4', None)
        assert ep.to_string() == 'http://1.2.3.4'

    def test_none_route_omitted(self, _mock_ssl):
        ep = Endpoint('1.2.3.4', 80)
        assert ep.to_string() == 'http://1.2.3.4:80'

    def test_all_none(self, _mock_ssl):
        ep = Endpoint(None, None)
        assert ep.to_string() == 'http://localhost'


class TestEndpointCall:
    def test_call_creates_new_with_route(self):
        ep = Endpoint('1.2.3.4', 80)
        ep2 = ep('/foo')
        assert ep2.route == 'foo'
        assert ep.route is None  # original unchanged

    def test_call_with_none_returns_self(self):
        ep = Endpoint('1.2.3.4', 80)
        assert ep(None) is ep

    def test_call_with_empty_returns_self(self):
        ep = Endpoint('1.2.3.4', 80)
        assert ep('') is ep

    def test_call_normalizes_slash(self):
        ep = Endpoint('1.2.3.4', 80)
        ep2 = ep('/bar')
        assert ep2.route == 'bar'


class TestEndpointIter:
    def test_full(self):
        ep = Endpoint('1.2.3.4', 80, 'route')
        assert tuple(ep) == ('1.2.3.4', 80, 'route')

    def test_none_ip_yields_localhost(self):
        ep = Endpoint(None, 80)
        result = tuple(ep)
        assert result[0] == 'localhost'

    def test_none_port_skipped(self):
        ep = Endpoint('1.2.3.4', None, 'route')
        assert tuple(ep) == ('1.2.3.4', 'route')

    def test_none_route_skipped(self):
        ep = Endpoint('1.2.3.4', 80)
        assert tuple(ep) == ('1.2.3.4', 80)

    def test_only_ip(self):
        ep = Endpoint('1.2.3.4', None, None)
        assert tuple(ep) == ('1.2.3.4',)


@patch('shared.ssl_utils.get_ssl_context', return_value=None)
class TestEndpointStringMethods:
    def test_str(self, _mock_ssl):
        ep = Endpoint('1.2.3.4', 80)
        assert str(ep) == 'http://1.2.3.4:80'

    def test_repr(self, _mock_ssl):
        ep = Endpoint('1.2.3.4', 80)
        assert repr(ep) == 'http://1.2.3.4:80'
