"""A demo Python client for the Antseed gateway API.

The gateway is OpenAI- and Anthropic-compatible at ``/v1`` (see
antseed.com/docs/gateway/api). Every request carries an API key as
``Authorization: Bearer <key>``; the key decides who pays, which budgets and
routing policies apply, and where the request is logged.

The default base URL is a local gateway (``http://localhost:8379/v1``) —
Antseed has no hosted public gateway; every user runs their own (or points
the client at their own domain's ``/v1``). Set ``ANTSEED_BASE_URL`` /
``ANTSEED_API_KEY`` or pass them explicitly.

Scope of this demo: model listing, chat completions, and key usage/cost.
Streaming, Responses API, Anthropic messages, images, audio, video jobs and
x402 top-ups are deliberately left for the full SDK (see README).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

from .errors import AntseedError
from .models import ChatCompletion, KeyUsage, Model, Usage

DEFAULT_BASE_URL = "http://localhost:8379/v1"

__all__ = [
    "AntseedClient",
    "pin_model",
]


def pin_model(peer_id: str, model: str) -> str:
    """Build a pinned model id: ``<peerId>@<model>``.

    The peer id is lowercase without ``0x`` (per the models doc). A bare
    model id (``deepseek-v4-flash``) means automatic routing instead.
    """
    return f"{peer_id.lower().removeprefix('0x')}@{model}"


class AntseedClient:
    """Client for one Antseed gateway.

    Args:
        api_key: gateway API key (``antseed_…``). If omitted, read from the
            ``ANTSEED_API_KEY`` environment variable.
        base_url: gateway base URL, with or without the trailing ``/v1``.
            Defaults to ``ANTSEED_BASE_URL`` or ``http://localhost:8379/v1``.
        timeout: default per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        key = api_key or os.environ.get("ANTSEED_API_KEY")
        if not key:
            raise ValueError(
                "No API key: pass api_key=... or set ANTSEED_API_KEY. "
                "Create one in the gateway console (Keys → Create key) or "
                "with `antseed gateway key create`."
            )
        self.api_key = key
        self.base_url = self._normalize_base_url(
            base_url or os.environ.get("ANTSEED_BASE_URL") or DEFAULT_BASE_URL
        )
        self.timeout = timeout

    @classmethod
    def from_env(cls, **kwargs: Any) -> "AntseedClient":
        """Build a client purely from ``ANTSEED_API_KEY`` / ``ANTSEED_BASE_URL``."""
        return cls(**kwargs)

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        url = url.strip().rstrip("/")
        if not url.endswith("/v1"):
            url += "/v1"
        return url

    # -- low-level transport -------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.api_key}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            req.add_header(name, value)
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout if timeout is None else timeout
            ) as resp:
                return resp.status, dict(resp.headers.items()), resp.read()
        except urllib.error.HTTPError as exc:
            raise AntseedError.from_response(exc.code, exc.read()) from exc
        except urllib.error.URLError as exc:
            raise AntseedError(
                f"Could not reach the gateway at {self.base_url}: {exc.reason}",
                status=None,
            ) from exc

    def _get_json(self, path: str, **kwargs: Any) -> dict:
        status, _headers, body = self._request("GET", path, **kwargs)
        return _parse_json(body, path, status)

    def _post_json(
        self, path: str, body: dict, **kwargs: Any
    ) -> tuple[dict, dict[str, str]]:
        status, headers, raw = self._request("POST", path, body=body, **kwargs)
        return _parse_json(raw, path, status), headers

    # -- models ---------------------------------------------------------------

    def list_models(self, type: str | None = None) -> list[Model]:
        """List the models on the network (``GET /v1/models``).

        Free (no spend), but still needs a key. With a key limited to
        certain models, only those are listed. ``type`` filters the listing
        — ``"text"``, ``"speech"``, ``"image"``, ``"video"`` or ``"router"``
        (``GET /v1/models?type=router`` lists routing services, each with
        the ``model`` value, protocol and accepted ``routing`` options).
        """
        path = "/models"
        if type:
            path += f"?type={type}"
        payload = self._get_json(path)
        return [Model.from_dict(entry) for entry in (payload.get("data") or [])]

    # -- chat completions ------------------------------------------------------

    def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        routing: dict | None = None,
        user: str | None = None,
        end_user: str | None = None,
        timeout: float | None = None,
    ) -> ChatCompletion:
        """One OpenAI-compatible chat completion (``POST /v1/chat/completions``).

        Args:
            model: a bare id for automatic routing (``"deepseek-v4-flash"``),
                a pinned id (``"<peerId>@deepseek-v4-flash"`` — see
                :func:`pin_model`), or a router model
                (``"<routerPeerId>@<routerServiceId>"``).
            messages: OpenAI-style ``[{"role": "user", "content": "..."}]``.
            temperature: sampling temperature, passed through when given.
            max_tokens: max output tokens, passed through when given.
            routing: router settings in the router's protocol terms, e.g.
                ``{"cost_quality_tradeoff": 7}`` for an ``irp-suggest``
                router (0 = best quality, 10 = cheapest).
            user: OpenAI-style ``user`` field, recorded in the request log.
            end_user: attribution header ``x-antseed-end-user`` — recorded
                in the request log, not forwarded to the provider.
        Returns:
            A :class:`ChatCompletion` with ``.text``, ``.usage`` and
            ``.gateway_tag`` (the ``x-antseed-gateway-tag`` response header,
            the request's tag in the management API).
        """
        body: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if routing is not None:
            body["routing"] = routing
        if user is not None:
            body["user"] = user
        headers = (
            {"x-antseed-end-user": end_user} if end_user is not None else None
        )
        payload, resp_headers = self._post_json(
            "/chat/completions", body, headers=headers, timeout=timeout
        )
        return ChatCompletion.from_dict(
            payload, gateway_tag=_header(resp_headers, "x-antseed-gateway-tag")
        )

    # -- usage & cost ----------------------------------------------------------

    def get_key_usage(self) -> KeyUsage:
        """Usage and limits of the calling key (``GET /v1/key``).

        Returns spent/request/token totals plus daily/weekly/monthly/total
        limits — the key's own limits (the lower of the admins' and the
        owner's). Member and workspace budgets can stop a request first.
        """
        return KeyUsage.from_dict(self._get_json("/key"))

    def estimate_cost(
        self, model: Model, usage: Usage, peer_id: str | None = None
    ) -> Decimal | None:
        """Estimated USD for a call, from usage x the model's peer pricing.

        Delegates to :meth:`Model.estimate_cost`; see there for the rules.
        Returns ``None`` when the model lists no per-token pricing.
        """
        return model.estimate_cost(usage, peer_id=peer_id)


def _parse_json(body: bytes, path: str, status: int) -> dict:
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AntseedError(
            f"Gateway returned a non-JSON answer for {path} (HTTP {status})",
            status=status,
        ) from exc
    if not isinstance(parsed, dict):
        raise AntseedError(
            f"Gateway returned an unexpected answer for {path} (HTTP {status})",
            status=status,
        )
    return parsed


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = {k.lower(): v for k, v in headers.items()}
    return lowered.get(name.lower())
