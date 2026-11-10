"""Demo Python SDK for the Antseed gateway API.

Antseed is a peer-to-peer AI-inference network. Its gateway serves an
OpenAI- and Anthropic-compatible API at ``/v1``; every request carries an
API key as ``Authorization: Bearer <key>``. This demo package covers the
core calls — model listing, chat completions, and key usage/cost — with
zero runtime dependencies (stdlib ``urllib`` only).

See README.md for the install and quickstart. The full SDK scope
(streaming, Responses API, Anthropic messages, images, audio, video jobs,
x402 top-ups) is deliberately left out of this demo.
"""

from .client import AntseedClient, pin_model
from .errors import (
    AntseedError,
    AuthenticationError,
    InsufficientFundsError,
    NotFoundError,
    PaymentRequiredError,
    ProviderUnavailableError,
    RateLimitError,
)
from .models import (
    ChatCompletion,
    KeyPeriodUsage,
    KeyUsage,
    Model,
    PeerOffer,
    Usage,
)

__all__ = [
    "AntseedClient",
    "pin_model",
    "AntseedError",
    "AuthenticationError",
    "InsufficientFundsError",
    "NotFoundError",
    "PaymentRequiredError",
    "ProviderUnavailableError",
    "RateLimitError",
    "ChatCompletion",
    "KeyPeriodUsage",
    "KeyUsage",
    "Model",
    "PeerOffer",
    "Usage",
]

__version__ = "0.1.0"
