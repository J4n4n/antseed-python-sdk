"""Antseed gateway errors.

The gateway answers failures with an OpenAI-style envelope::

    {"error": {"message": "...", "type": "...", "code": "..."}}

(verified in ``apps/cli/src/gateway/server.ts`` — ``sendJson(res, status,
{error: {message, type, code}})``). Some upstreams return ``{"error": "..."}``
or plain text instead; :func:`AntseedError.from_response` normalises all of
them. Status codes follow the public docs (antseed.com/docs/gateway/api):
401 unknown/revoked/expired key, 404 unknown path, 502 peer not reachable.
"""

from __future__ import annotations


class AntseedError(Exception):
    """Base error for every gateway failure.

    Attributes:
        status: HTTP status code, or ``None`` when the request never reached
            the gateway (connection error, timeout).
        code: machine-readable error code from the gateway, if any.
        type: error type string from the gateway, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: str | None = None,
        type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.type = type

    def __str__(self) -> str:  # pragma: no cover - trivial
        parts = [self.message]
        if self.code:
            parts.append(f"({self.code})")
        if self.status is not None:
            parts.append(f"[HTTP {self.status}]")
        return " ".join(parts)

    @classmethod
    def from_response(cls, status: int, body: bytes) -> "AntseedError":
        """Build the most specific error for an HTTP failure response."""
        import json

        message: str | None = None
        code: str | None = None
        err_type: str | None = None
        try:
            parsed = json.loads(body.decode("utf-8", "replace"))
        except (ValueError, UnicodeDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                raw = err.get("message")
                message = str(raw) if raw is not None else None
                code = _as_str(err.get("code"))
                err_type = _as_str(err.get("type"))
            elif isinstance(err, str):
                message = err
            elif isinstance(parsed.get("message"), str):
                message = parsed["message"]
        if message is None:
            text = body.decode("utf-8", "replace").strip()
            message = text or f"Gateway request failed with HTTP {status}"
        exc_cls = _class_for_status(status, code)
        return exc_cls(message, status=status, code=code, type=err_type)


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _class_for_status(status: int, code: str | None) -> type[AntseedError]:
    if status == 401:
        return AuthenticationError
    if status == 402:
        return PaymentRequiredError
    if status == 404:
        return NotFoundError
    if status == 429:
        return RateLimitError
    if status == 502:
        return ProviderUnavailableError
    if code == "insufficient_deposits":
        return InsufficientFundsError
    return AntseedError


class AuthenticationError(AntseedError):
    """401 — missing, unknown, revoked or expired API key."""


class PaymentRequiredError(AntseedError):
    """402 — the gateway wants payment (x402 top-up flow)."""


class NotFoundError(AntseedError):
    """404 — unknown path (anything outside the documented routes)."""


class RateLimitError(AntseedError):
    """429 — the gateway rate-limited the request."""


class ProviderUnavailableError(AntseedError):
    """502 — the pinned provider / router peer is not reachable."""


class InsufficientFundsError(AntseedError):
    """The key's wallet cannot cover the request (``insufficient_deposits``)."""
