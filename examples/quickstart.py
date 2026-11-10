#!/usr/bin/env python3
"""Quickstart example for the Antseed Python SDK (demo).

Lists the models on your gateway, picks the cheapest text model, sends
one chat completion, and prints the token usage plus the estimated cost
(from the model's peer pricing) and the key's real spend so far.

Run against your own gateway (needs a key — no spend beyond the one call):

    export ANTSEED_API_KEY=antseed_...
    export ANTSEED_BASE_URL=http://localhost:8379/v1   # optional, this is the default
    python examples/quickstart.py

Or against the local stub gateway (no key, no spend, for demoing the SDK):

    python -m tests.stub_gateway   # in another terminal; note the base URL
    ANTSEED_API_KEY=antseed_demo ANTSEED_BASE_URL=http://127.0.0.1:<port>/v1 \\
        python examples/quickstart.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from antseed import AntseedClient, AuthenticationError, pin_model  # noqa: E402


def main() -> int:
    if not os.environ.get("ANTSEED_API_KEY"):
        print("No ANTSEED_API_KEY set.")
        print("Create a key in the gateway console (Keys -> Create key) or run:")
        print("  antseed gateway key create --label demo")
        print("then:  export ANTSEED_API_KEY=antseed_...")
        print()
        print("To see the SDK work without a gateway, run the stub instead:")
        print("  python -m tests.stub_gateway")
        return 0

    client = AntseedClient.from_env()

    models = client.list_models()
    print(f"Gateway {client.base_url}: {len(models)} model(s)")
    text_models = [m for m in models if m.type == "text"]
    if not text_models:
        print("No text models listed for this key.")
        return 0
    model = text_models[0]
    cheapest = model.cheapest_peer()
    print(f"Using model {model.id!r} ({model.name})")
    if cheapest is not None:
        print(
            f"  cheapest peer: {cheapest.display_name} "
            f"(${cheapest.input_usd_per_million}/M in, "
            f"${cheapest.output_usd_per_million}/M out)"
        )
        print(f"  pinned id: {pin_model(cheapest.peer_id, model.id)}")

    reply = client.chat_completion(
        model=model.id,
        messages=[
            {"role": "user", "content": "In one sentence, what is Antseed?"}
        ],
    )
    print()
    print("Reply:", reply.text)
    print(
        f"Usage: {reply.usage.prompt_tokens} in + "
        f"{reply.usage.completion_tokens} out "
        f"({reply.usage.cached_input_tokens} cached in)"
    )
    if reply.gateway_tag:
        print("Gateway tag:", reply.gateway_tag)
    cost = client.estimate_cost(model, reply.usage)
    if cost is not None:
        print(f"Estimated cost of this call: ${cost}")
    else:
        print("No per-token pricing listed for this model, cost unknown.")

    key = client.get_key_usage()
    print(
        f"Key {key.label!r}: {key.requests} requests, "
        f"${key.spent_usd} spent so far."
    )
    daily = key.limits.get("daily")
    if daily and daily.remaining_usd is not None:
        print(f"Daily budget remaining: ${daily.remaining_usd}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuthenticationError as exc:
        print(f"Authentication failed: {exc}")
        print("Check ANTSEED_API_KEY — keys are shown once when created.")
        raise SystemExit(1)
