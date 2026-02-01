from __future__ import annotations


class PukError(Exception):
    """Base error for PUK with an optional exit code."""

    exit_code: int = 1

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code


class MissingInfoError(PukError):
    exit_code = 2


class PolicyViolationError(PukError):
    exit_code = 3


class ToolExecutionError(PukError):
    exit_code = 4


class ProviderAuthError(PukError):
    exit_code = 5


class UserAbortError(PukError):
    exit_code = 1
