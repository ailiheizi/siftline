from __future__ import annotations

from .models import ErrorItem


class ProviderHTTPError(Exception):
    """A classified failure raised by a provider or the HTTP transport."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        cause: str | None = None,
        provider: str = "http",
        preflight: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.cause = cause
        self.provider = provider
        # True when the request was rejected locally, before any provider or
        # external transport call (missing credentials, unsupported operation,
        # unavailable local transport, explicit validation). Such events never
        # count as provider calls in the machine research ledger.
        self.preflight = preflight

    def to_error(self, provider: str, operation: str | None = None) -> ErrorItem:
        return ErrorItem(
            code=self.code,
            message=self.message,
            provider=provider,
            operation=operation,
            severity="error",
            retryable=self.retryable,
            status_code=self.status_code,
            cause=self.cause,
        )
