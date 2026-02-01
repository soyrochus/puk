"""Tests for puk.errors module."""
from __future__ import annotations

import pytest

from puk.errors import (
    MissingInfoError,
    PolicyViolationError,
    ProviderAuthError,
    PukError,
    ToolExecutionError,
    UserAbortError,
)


class TestPukError:
    def test_base_error_default_exit_code(self):
        err = PukError("test error")
        assert str(err) == "test error"
        assert err.exit_code == 1

    def test_base_error_custom_exit_code(self):
        err = PukError("test error", exit_code=42)
        assert err.exit_code == 42

    def test_base_error_is_exception(self):
        err = PukError("test")
        assert isinstance(err, Exception)


class TestMissingInfoError:
    def test_default_exit_code(self):
        err = MissingInfoError("missing info")
        assert err.exit_code == 2

    def test_inherits_from_puk_error(self):
        err = MissingInfoError("test")
        assert isinstance(err, PukError)


class TestPolicyViolationError:
    def test_default_exit_code(self):
        err = PolicyViolationError("policy violated")
        assert err.exit_code == 3

    def test_inherits_from_puk_error(self):
        err = PolicyViolationError("test")
        assert isinstance(err, PukError)


class TestToolExecutionError:
    def test_default_exit_code(self):
        err = ToolExecutionError("tool failed")
        assert err.exit_code == 4

    def test_inherits_from_puk_error(self):
        err = ToolExecutionError("test")
        assert isinstance(err, PukError)


class TestProviderAuthError:
    def test_default_exit_code(self):
        err = ProviderAuthError("auth failed")
        assert err.exit_code == 5

    def test_inherits_from_puk_error(self):
        err = ProviderAuthError("test")
        assert isinstance(err, PukError)


class TestUserAbortError:
    def test_default_exit_code(self):
        err = UserAbortError("user aborted")
        assert err.exit_code == 1

    def test_inherits_from_puk_error(self):
        err = UserAbortError("test")
        assert isinstance(err, PukError)


class TestErrorRaising:
    def test_can_catch_specific_error(self):
        with pytest.raises(PolicyViolationError):
            raise PolicyViolationError("test")

    def test_can_catch_as_base_error(self):
        with pytest.raises(PukError):
            raise ToolExecutionError("test")

    def test_can_catch_as_exception(self):
        with pytest.raises(Exception):
            raise MissingInfoError("test")
