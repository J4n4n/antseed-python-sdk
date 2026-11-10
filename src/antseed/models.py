"""Typed shapes for the Antseed gateway API.

Field names follow the gateway's own wire format, verified against the
repo:

* ``/v1/models`` entries — ``apps/cli/src/proxy/network-models.ts``
  (``NetworkModelEntry`` / ``NetworkModelPeerOffer`` / ``NetworkRouterEntry``).
  Every model appears once, with the peers that serve it (and their pricing)
  under ``peers``. Each peer keeps its advertised ``serviceId``; pin a
  provider as ``<peerId>@<serviceId>``.
* ``/v1/chat/completions`` — OpenAI-compatible.
* ``/v1/key`` — the usage/limits payload shown in the public API docs
  (antseed.com/docs/gateway/api).

Money is ``Decimal`` everywhere: the gateway returns USD amounts as decimal
strings (e.g. ``"1.204310"``) and per-token prices as numbers per million
tokens, so float rounding would silently corrupt cost math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


@dataclass
class PeerOffer:
    """One provider's offer for a model, as listed under ``peers``."""

    peer_id: str
    display_name: str | None = None
    provider: str | None = None
    service_id: str | None = None
    protocol: str | None = None
    protocols: list[str] = field(default_factory=list)
    type: str | None = None
    reputation_score: float | None = None
    effective_reputation_score: float | None = None
    on_chain_reputation_score: float | None = None
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None
    cached_input_usd_per_million: float | None = None
    min_image_usd_per_image: float | None = None
    max_image_usd_per_image: float | None = None
    free_tier: dict | None = None
    # Router offers (``?type=router``): the ``model`` value to send, the
    # routing protocol, and the per-request price.
    model: str | None = None
    price_usd_per_request: float | None = None
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "PeerOffer":
        return cls(
            peer_id=str(data.get("peerId", "")),
            display_name=data.get("displayName"),
            provider=data.get("provider"),
            service_id=data.get("serviceId"),
            protocol=data.get("protocol"),
            protocols=list(data.get("protocols") or []),
            type=data.get("type"),
            reputation_score=data.get("reputationScore"),
            effective_reputation_score=data.get("effectiveReputationScore"),
            on_chain_reputation_score=data.get("onChainReputationScore"),
            input_usd_per_million=data.get("inputUsdPerMillion"),
            output_usd_per_million=data.get("outputUsdPerMillion"),
            cached_input_usd_per_million=data.get("cachedInputUsdPerMillion"),
            min_image_usd_per_image=data.get("minImageUsdPerImage"),
            max_image_usd_per_image=data.get("maxImageUsdPerImage"),
            free_tier=data.get("freeTier"),
            model=data.get("model"),
            price_usd_per_request=data.get("priceUsdPerRequest"),
            raw=dict(data),
        )

    def pin(self, model_id: str) -> str:
        """The pinned model id for this peer: ``<peerId>@<modelId>``."""
        return f"{self.peer_id}@{model_id}"

    @property
    def is_free(self) -> bool:
        """True when the offer is priced at zero (free tier / free offer)."""
        return (
            self.input_usd_per_million == 0 and self.output_usd_per_million == 0
        ) or bool(self.free_tier)


@dataclass
class CapabilityCoverage:
    total_offers: int = 0
    context_length: int = 0
    max_output_tokens: int = 0
    input_modalities: int = 0
    output_modalities: int = 0
    reasoning: int = 0
    tool_use: int = 0
    structured_output: int = 0
    supported_parameters: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "CapabilityCoverage":
        data = data or {}
        return cls(
            total_offers=int(data.get("total_offers", 0)),
            context_length=int(data.get("context_length", 0)),
            max_output_tokens=int(data.get("max_output_tokens", 0)),
            input_modalities=int(data.get("input_modalities", 0)),
            output_modalities=int(data.get("output_modalities", 0)),
            reasoning=int(data.get("reasoning", 0)),
            tool_use=int(data.get("tool_use", 0)),
            structured_output=int(data.get("structured_output", 0)),
            supported_parameters=int(data.get("supported_parameters", 0)),
        )


@dataclass
class Model:
    """One entry of ``GET /v1/models``."""

    id: str
    name: str | None = None
    aliases: list[str] = field(default_factory=list)
    object: str = "model"
    created: int | None = None
    owned_by: str = "antseed"
    type: str | None = None  # "text" | "speech" | "image" | "video" | "router"
    supported_protocols: list[str] = field(default_factory=list)
    context_length: int | None = None
    max_output_tokens: int | None = None
    architecture: dict | None = None
    capabilities: dict | None = None
    supported_parameters: list[str] = field(default_factory=list)
    voices: list[str] = field(default_factory=list)
    capability_coverage: CapabilityCoverage = field(
        default_factory=CapabilityCoverage
    )
    peers: list[PeerOffer] = field(default_factory=list)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Model":
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name"),
            aliases=list(data.get("aliases") or []),
            object=str(data.get("object", "model")),
            created=data.get("created"),
            owned_by=str(data.get("owned_by", "antseed")),
            type=data.get("type"),
            supported_protocols=list(data.get("supported_protocols") or []),
            context_length=data.get("context_length"),
            max_output_tokens=data.get("max_output_tokens"),
            architecture=data.get("architecture"),
            capabilities=data.get("capabilities"),
            supported_parameters=list(data.get("supported_parameters") or []),
            voices=list(data.get("voices") or []),
            capability_coverage=CapabilityCoverage.from_dict(
                data.get("capability_coverage")
            ),
            peers=[PeerOffer.from_dict(p) for p in (data.get("peers") or [])],
            raw=dict(data),
        )

    def peer(self, peer_id: str) -> PeerOffer | None:
        """The offer from one peer, by its (lowercase, no ``0x``) peer id."""
        peer_id = peer_id.lower().removeprefix("0x")
        for offer in self.peers:
            if offer.peer_id.lower().removeprefix("0x") == peer_id:
                return offer
        return None

    def cheapest_peer(self) -> PeerOffer | None:
        """The offer with the lowest input price (ties: lowest output price)."""
        priced = [p for p in self.peers if p.input_usd_per_million is not None]
        if not priced:
            return self.peers[0] if self.peers else None
        return min(
            priced,
            key=lambda p: (
                p.input_usd_per_million or 0,
                p.output_usd_per_million or 0,
            ),
        )

    def estimate_cost(self, usage: "Usage", peer_id: str | None = None) -> Decimal | None:
        """Estimated USD for a call, from token usage x peer pricing.

        Uses the pinned peer when ``peer_id`` is given, else the cheapest
        peer. Returns ``None`` when the model lists no per-token pricing
        (routers charge per ranking instead — see ``price_usd_per_request``).
        Cached input tokens are billed at the cached rate when the peer
        publishes one, else at the normal input rate.
        """
        offer = self.peer(peer_id) if peer_id else self.cheapest_peer()
        if offer is None or offer.input_usd_per_million is None:
            return None
        per_million = Decimal("1000000")
        input_tokens = usage.prompt_tokens - (usage.cached_input_tokens or 0)
        cost = Decimal(str(input_tokens)) * Decimal(
            str(offer.input_usd_per_million)
        ) / per_million
        if usage.cached_input_tokens:
            cached_rate = offer.cached_input_usd_per_million
            if cached_rate is None:
                cached_rate = offer.input_usd_per_million
            cost += Decimal(str(usage.cached_input_tokens)) * Decimal(
                str(cached_rate)
            ) / per_million
        if offer.output_usd_per_million is not None:
            cost += Decimal(str(usage.completion_tokens)) * Decimal(
                str(offer.output_usd_per_million)
            ) / per_million
        return cost


@dataclass
class Usage:
    """Token usage reported by a completion.

    ``cached_input_tokens`` is the cached share of the input (the gateway
    tracks it separately — see ``ResponseTokens`` in the repo); it is
    included in ``prompt_tokens``.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict | None) -> "Usage":
        data = data or {}
        cached = 0
        details = data.get("prompt_tokens_details")
        if isinstance(details, dict):
            cached = int(details.get("cached_tokens", 0))
        elif isinstance(data.get("cached_input_tokens"), int):
            cached = int(data["cached_input_tokens"])
        total = int(data.get("total_tokens", 0))
        prompt = int(data.get("prompt_tokens", 0))
        completion = int(data.get("completion_tokens", 0))
        if total == 0:
            total = prompt + completion
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cached_input_tokens=cached,
        )


@dataclass
class ChatCompletion:
    """The result of ``POST /v1/chat/completions`` (OpenAI-compatible)."""

    id: str | None = None
    model: str | None = None
    text: str = ""
    choices: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None
    gateway_tag: str | None = None  # ``x-antseed-gateway-tag`` response header
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict, gateway_tag: str | None = None) -> "ChatCompletion":
        choices = data.get("choices") or []
        text = ""
        finish_reason = None
        if choices:
            message = choices[0].get("message") or {}
            text = message.get("content") or ""
            finish_reason = choices[0].get("finish_reason")
        return cls(
            id=data.get("id"),
            model=data.get("model"),
            text=text,
            choices=choices,
            usage=Usage.from_dict(data.get("usage")),
            finish_reason=finish_reason,
            gateway_tag=gateway_tag,
            raw=dict(data),
        )


@dataclass
class KeyPeriodUsage:
    limit_usd: Decimal | None = None
    spent_usd: Decimal = Decimal("0")
    remaining_usd: Decimal | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "KeyPeriodUsage":
        data = data or {}
        return cls(
            limit_usd=_decimal(data.get("limit_usd")),
            spent_usd=_decimal(data.get("spent_usd")) or Decimal("0"),
            remaining_usd=_decimal(data.get("remaining_usd")),
        )


@dataclass
class KeyUsage:
    """The ``GET /v1/key`` payload: usage and limits of the calling key."""

    id: str | None = None
    label: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    topup_enabled: bool = False
    buyer_address: str | None = None
    requests: int = 0
    spent_usd: Decimal = Decimal("0")
    topped_up_usd: Decimal = Decimal("0")
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    limits: dict[str, KeyPeriodUsage] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "KeyUsage":
        payload = data.get("data", data) if isinstance(data, dict) else {}
        usage = payload.get("usage") or {}
        limits = {
            period: KeyPeriodUsage.from_dict(values)
            for period, values in (payload.get("limits") or {}).items()
        }
        return cls(
            id=payload.get("id"),
            label=payload.get("label"),
            created_at=payload.get("created_at"),
            expires_at=payload.get("expires_at"),
            topup_enabled=bool(payload.get("topup_enabled", False)),
            buyer_address=payload.get("buyer_address"),
            requests=int(usage.get("requests", 0)),
            spent_usd=_decimal(usage.get("spent_usd")) or Decimal("0"),
            topped_up_usd=_decimal(usage.get("topped_up_usd")) or Decimal("0"),
            input_tokens=int(usage.get("input_tokens", 0)),
            cached_input_tokens=int(usage.get("cached_input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            limits=limits,
            raw=dict(data),
        )
