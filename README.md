# antseed — demo Python SDK for the Antseed gateway

> **Demo sample, not the full SDK.** This package was built to show the
> Antseed team what a native Python SDK would look like, as part of a
> micro-grant pitch. It is not published, not affiliated with Antseed, and
> covers only the core calls. See [What's left out](#whats-left-out).

Antseed is a peer-to-peer AI-inference network. Its gateway serves an
OpenAI- and Anthropic-compatible API at `/v1`; every request carries an API
key as `Authorization: Bearer <key>`, and the key decides who pays, which
budgets and routing policies apply, and where the request is logged.
Antseed's own docs point Python developers at the raw OpenAI/Anthropic
clients via a base URL — there is no native Python SDK. This demo fills
that gap: a small, typed, zero-dependency client.

## Install

Requires Python 3.10+. No runtime dependencies (stdlib `urllib` only).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Quickstart

Antseed has no hosted public gateway — you run your own
(`http://localhost:8379/v1` by default) or point at your own domain's
`/v1`. Create a key in the gateway console (**Keys → Create key**) or with
`antseed gateway key create`, then:

```bash
export ANTSEED_API_KEY=antseed_...
export ANTSEED_BASE_URL=http://localhost:8379/v1   # optional, the default
python examples/quickstart.py
```

```python
from antseed import AntseedClient, pin_model

client = AntseedClient.from_env()  # ANTSEED_API_KEY / ANTSEED_BASE_URL

# 1. What can this key call? (free, no spend)
models = client.list_models()
text = next(m for m in models if m.type == "text")
cheapest = text.cheapest_peer()
print(cheapest.display_name, cheapest.input_usd_per_million)

# 2. One chat completion — bare id = automatic routing,
#    pinned id = one provider: pin_model(peer_id, model_id)
reply = client.chat_completion(
    model=text.id,
    messages=[{"role": "user", "content": "Hello"}],
)
print(reply.text)
print(reply.usage)        # prompt/completion/total tokens (+ cached input)
print(reply.gateway_tag)  # x-antseed-gateway-tag response header

# 3. What did it cost? (estimated from the model's peer pricing)
print(client.estimate_cost(text, reply.usage))

# 4. What has this key spent in total? (GET /v1/key)
key = client.get_key_usage()
print(key.spent_usd, key.limits["daily"].remaining_usd)
```

Routing services work the same way — list them with
`client.list_models(type="router")` and pass the router model plus a
`routing` object, e.g. `routing={"cost_quality_tradeoff": 7}` for an
`irp-suggest` router (0 = best quality, 10 = cheapest).

## What's implemented

| Call | Method |
|---|---|
| `list_models(type=None)` | `GET /v1/models` — full entries: peers, per-token pricing (`inputUsdPerMillion` / `outputUsdPerMillion`), capabilities, aliases; `type="router"` / `"speech"` filters |
| `chat_completion(...)` | `POST /v1/chat/completions` — OpenAI-compatible messages in; text, usage, finish reason and `x-antseed-gateway-tag` out; `routing`, `user`, `x-antseed-end-user` supported |
| `get_key_usage()` | `GET /v1/key` — requests, spent/topped-up USD, token totals, daily/weekly/monthly/total limits (all money as `Decimal`) |
| `Model.estimate_cost(usage, peer_id=None)` / `client.estimate_cost(...)` | Cost from token usage × peer pricing (cheapest peer by default; cached input billed at the cached rate when published) |
| `pin_model(peer_id, model)` | Builds `<peerId>@<model>` pinned ids |
| Errors | OpenAI-style `{error: {message, type, code}}` mapped to typed exceptions: 401 `AuthenticationError`, 402 `PaymentRequiredError`, 404 `NotFoundError`, 429 `RateLimitError`, 502 `ProviderUnavailableError`, `insufficient_deposits` → `InsufficientFundsError` |

## Verification status — read this

**Nothing here was verified live against a real gateway.** Antseed has no
hosted public gateway: every user runs their own, and starting one needs
the node software plus a funded wallet. No key was bought, no account was
created, and no money was spent while building this demo.

What *was* verified, over real HTTP against a local stub gateway
(`tests/stub_gateway.py`): the client's wire behaviour — request shapes,
the `Authorization: Bearer` header, response parsing, cost math, and error
mapping. The stub's fixtures are shaped from the real gateway's own code
and docs (the `/v1/models` entry shape from
`apps/cli/src/proxy/network-models.ts`, the repo's own fake gateway in
`apps/cli/src/gateway/chat/routes.test.ts`, and the `/v1/key` example from
the public API docs). Run the suite with:

```bash
python -m unittest discover -s tests -v
```

To see the example run end-to-end without a gateway, start the stub in one
terminal (`python -m tests.stub_gateway`, demo key `antseed_demo`) and run
the example against its base URL (see the header of
`examples/quickstart.py`).

## What's left out

Deliberately demo-scoped; the full SDK would add:

- Streaming chat completions (SSE) and the Responses API (`/v1/responses`)
- Anthropic messages (`/v1/messages`, `/v1/messages/count_tokens`)
- Images (`/v1/images/generations`, `/v1/images/edits`), audio
  (`/v1/audio/speech`), and video jobs (`/api/v1/video/*`, `/fal/v1/video/*`)
- x402 key top-up (`POST /v1/key/topup`)
- Async client, retries/backoff, and pagination helpers
- A published package (PyPI) with type stubs and full docs

## Sources

- API behaviour: <https://antseed.com/docs/gateway/api> and the repo's
  gateway code (`apps/cli/src/gateway/`, `apps/cli/src/proxy/network-models.ts`)
  at <https://github.com/AntSeed/antseed>
- No OpenAPI document exists for the gateway (verified: no OpenAPI spec in
  the repo or docs) — the shapes above were read from the TypeScript
  sources, not generated.
