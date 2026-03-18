"""Tests for shared/parameters.py — get_parameters() and is_type()."""
import pytest
from shared.parameters import get_parameters, is_type
from shared.exceptions import ParameterError, InvalidParameter


class TestGetParametersDict:
    def test_simple_extraction(self):
        result = get_parameters({'a': 1, 'b': 2}, 'a', 'b')
        assert result == (1, 2)

    def test_single_key(self):
        result = get_parameters({'x': 'hello'}, 'x')
        assert result == ('hello',)

    def test_missing_key_raises(self):
        with pytest.raises(ParameterError, match="not received"):
            get_parameters({'a': 1}, 'b')

    def test_with_validator_pass(self):
        result = get_parameters({'x': 5}, ('x', lambda v: v > 0))
        assert result == (5,)

    def test_with_validator_fail(self):
        with pytest.raises(InvalidParameter, match="failed validation"):
            get_parameters({'x': -1}, ('x', lambda v: v > 0))

    def test_default_validator_rejects_falsy(self):
        with pytest.raises(InvalidParameter):
            get_parameters({'x': ''}, 'x')

    def test_default_validator_rejects_zero(self):
        with pytest.raises(InvalidParameter):
            get_parameters({'x': 0}, 'x')

    def test_default_validator_accepts_truthy(self):
        result = get_parameters({'x': 'hello'}, 'x')
        assert result == ('hello',)


class TestGetParametersList:
    def test_no_validators(self):
        result = get_parameters([1, 2, 3], [])
        assert result == (1, 2, 3)

    def test_with_validators(self):
        result = get_parameters(
            [1, 'a'],
            [lambda x: isinstance(x, int), lambda x: isinstance(x, str)]
        )
        assert result == (1, 'a')

    def test_length_mismatch(self):
        with pytest.raises(ParameterError, match="Expected 2"):
            get_parameters([1], [lambda x: True, lambda x: True])

    def test_validator_failure(self):
        with pytest.raises(InvalidParameter):
            get_parameters([1], [lambda x: isinstance(x, str)])

    def test_none_validator_uses_truthy(self):
        result = get_parameters([42], [None])
        assert result == (42,)

    def test_none_validator_rejects_falsy(self):
        with pytest.raises(InvalidParameter):
            get_parameters([0], [None])

    def test_tuple_data(self):
        result = get_parameters((10, 20), [])
        assert result == (10, 20)


class TestGetParametersEdgeCases:
    def test_unsupported_type(self):
        with pytest.raises(NotImplementedError):
            get_parameters(42, 'a')

    def test_set_raises(self):
        with pytest.raises(NotImplementedError):
            get_parameters({1, 2}, 'a')


class TestIsType:
    def test_int(self):
        validator = is_type(int)
        assert validator(5) is True
        assert validator('hello') is False

    def test_str(self):
        validator = is_type(str)
        assert validator('hello') is True
        assert validator(5) is False

    def test_list(self):
        validator = is_type(list)
        assert validator([1, 2]) is True
        assert validator((1, 2)) is False
