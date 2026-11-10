"""A stub Antseed gateway for tests and the demo.

This is NOT the real gateway — it is a tiny local HTTP server that answers
exactly like the real one, so the client can be exercised end-to-end over
real HTTP without a gateway, a key, or any spend. Every fixture is shaped
from the real gateway's own sources:

* ``/v1/models`` entries follow ``NetworkModelEntry`` /
  ``NetworkModelPeerOffer`` (``apps/cli/src/proxy/network-models.ts``) and
  the repo's own fake gateway in
  ``apps/cli/src/gateway/chat/routes.test.ts``.
* The chat completion body is OpenAI-compatible.
* The ``/v1/key`` payload is the example from the public API docs
  (antseed.com/docs/gateway/api).
* Error bodies follow the gateway's envelope
  ``{"error": {"message", "type", "code"}}`` (``server.ts``).

Behaviour mirrors the docs: a missing/unknown key returns 401, unknown
paths return 404, and ``/v1/models`` is free (no spend) but still needs a
key. Run standalone to demo the example against it::

    python -m tests.stub_gateway   # prints the base URL, serves forever

The demo key accepted by the stub is ``antseed_demo`` (any key starting
with ``antseed_`` is accepted, mirroring the real key format).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEMO_KEY = "antseed_demo"

# One model with two peers (cheapest first in price, not in list order),
# one free model, and one router — the shapes the real gateway returns.
MODELS_FIXTURE = {
    "object": "list",
    "data": [
        {
            "id": "deepseek-v4-flash",
            "name": "DeepSeek V4 Flash",
            "aliases": ["deepseek-flash"],
            "object": "model",
            "created": 1790000000,
            "owned_by": "antseed",
            "type": "text",
            "supported_protocols": ["openai-chat", "anthropic-messages"],
            "context_length": 131072,
            "max_output_tokens": 8192,
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "capabilities": {
                "reasoning": False,
                "tool_use": True,
                "structured_output": True,
            },
            "supported_parameters": ["temperature", "max_tokens"],
            "capability_coverage": {
                "total_offers": 2,
                "context_length": 2,
                "max_output_tokens": 2,
                "input_modalities": 2,
                "output_modalities": 2,
                "reasoning": 2,
                "tool_use": 2,
                "structured_output": 2,
                "supported_parameters": 2,
            },
            "peers": [
                {
                    "peerId": "aa" * 20,
                    "displayName": "Peer One",
                    "provider": "peer-one",
                    "serviceId": "deepseek-v4-flash",
                    "protocol": "openai-chat",
                    "protocols": ["openai-chat"],
                    "type": "text",
                    "capabilities": {"toolUse": True},
                    "reputationScore": 87,
                    "effectiveReputationScore": 87,
                    "onChainReputationScore": None,
                    "inputUsdPerMillion": 2,
                    "outputUsdPerMillion": 10,
                },
                {
                    "peerId": "bb" * 20,
                    "displayName": "Peer Two",
                    "provider": "peer-two",
                    "serviceId": "deepseek-v4-flash",
                    "protocol": "openai-chat",
                    "protocols": ["openai-chat"],
                    "type": "text",
                    "capabilities": {"toolUse": True},
                    "reputationScore": 92,
                    "effectiveReputationScore": 92,
                    "onChainReputationScore": 90,
                    "inputUsdPerMillion": 1,
                    "outputUsdPerMillion": 5,
                    "cachedInputUsdPerMillion": 0.5,
                },
            ],
        },
        {
            "id": "free-model",
            "name": "Free Model",
            "aliases": [],
            "object": "model",
            "created": 1790000000,
            "owned_by": "antseed",
            "type": "text",
            "supported_protocols": ["openai-chat"],
            "context_length": 8192,
            "capability_coverage": {
                "total_offers": 1,
                "context_length": 1,
                "max_output_tokens": 1,
                "input_modalities": 1,
                "output_modalities": 1,
                "reasoning": 1,
                "tool_use": 0,
                "structured_output": 0,
                "supported_parameters": 1,
            },
            "peers": [
                {
                    "peerId": "cc" * 20,
                    "displayName": "Free Peer",
                    "provider": "free-peer",
                    "serviceId": "free-model",
                    "protocol": "openai-chat",
                    "protocols": ["openai-chat"],
                    "type": "text",
                    "reputationScore": 70,
                    "effectiveReputationScore": 70,
                    "onChainReputationScore": None,
                    "inputUsdPerMillion": 0,
                    "outputUsdPerMillion": 0,
                    "freeTier": {"program": "demo", "limit": 1000},
                }
            ],
        },
    ],
}

ROUTERS_FIXTURE = {
    "object": "list",
    "data": [
        {
            "id": "irp-suggest",
            "name": "IRP Suggest",
            "object": "model",
            "created": 1790000000,
            "owned_by": "antseed",
            "type": "router",
            "peers": [
                {
                    "peerId": "dd" * 20,
                    "displayName": "Router Peer",
                    "provider": "router-peer",
                    "serviceId": "irp-suggest",
                    "protocol": "irp-suggest",
                    "options": [
                        {
                            "name": "cost_quality_tradeoff",
                            "type": "number",
                            "min": 0,
                            "max": 10,
                            "default": 5,
                        }
                    ],
                    "model": "dddddddddddddddddddddddddddddddddddddddd@irp-suggest",
                    "priceUsdPerRequest": 0.001,
                    "models": ["deepseek-v4-flash", "free-model"],
                }
            ],
        }
    ],
}

CHAT_FIXTURE = {
    "id": "chatcmpl-demo",
    "object": "chat.completion",
    "created": 1790000000,
    "model": "deepseek-v4-flash",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello from the stub gateway.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 1000,
        "completion_tokens": 100,
        "total_tokens": 1100,
        "prompt_tokens_details": {"cached_tokens": 200},
    },
}

KEY_FIXTURE = {
    "data": {
        "id": "key_demo",
        "label": "Demo",
        "created_at": "2026-10-01T09:12:44.000Z",
        "expires_at": None,
        "topup_enabled": False,
        "buyer_address": "0x0000000000000000000000000000000000000000",
        "usage": {
            "requests": 42,
            "spent_usd": "1.204310",
            "topped_up_usd": "0.000000",
            "input_tokens": 180233,
            "cached_input_tokens": 90112,
            "output_tokens": 20118,
        },
        "limits": {
            "daily": {
                "limit_usd": "2.000000",
                "spent_usd": "0.410000",
                "remaining_usd": "1.590000",
            },
            "weekly": {
                "limit_usd": None,
                "spent_usd": "1.204310",
                "remaining_usd": None,
            },
            "monthly": {
                "limit_usd": None,
                "spent_usd": "1.204310",
                "remaining_usd": None,
            },
            "total": {
                "limit_usd": "100.000000",
                "spent_usd": "1.204310",
                "remaining_usd": "98.795690",
            },
        },
    }
}


class StubGatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    requests: list[dict] = []

    def log_message(self, *args):  # silence the server log
        pass

    def _send_json(self, status: int, payload: dict, extra: dict | None = None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self) -> bool:
        # Only the demo key is valid; any other key (even one shaped like
        # a real key) is unknown to the gateway -> 401, as the real one
        # answers for a missing/unknown/revoked/expired key.
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {DEMO_KEY}"

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    def _route(self, method: str):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        body = self._read_body() if method == "POST" else {}
        type(self).requests.append(
            {"method": method, "path": path, "query": query, "body": body,
             "headers": dict(self.headers.items())}
        )
        if not self._auth_ok():
            self._send_json(
                401,
                {"error": {"message": "Invalid API key",
                           "type": "authentication_error",
                           "code": "invalid_api_key"}},
            )
            return
        if method == "GET" and path == "/v1/models":
            if query.get("type") == ["router"]:
                self._send_json(200, ROUTERS_FIXTURE)
            else:
                self._send_json(200, MODELS_FIXTURE)
            return
        if method == "GET" and path == "/v1/key":
            self._send_json(200, KEY_FIXTURE)
            return
        if method == "POST" and path == "/v1/chat/completions":
            if body.get("model") == "missing-model":
                self._send_json(
                    502,
                    {"error": {"message": "peer not reachable",
                               "type": "server_error",
                               "code": "peer_not_reachable"}},
                )
                return
            self._send_json(
                200, CHAT_FIXTURE, extra={"x-antseed-gateway-tag": "req_demo"}
            )
            return
        self._send_json(
            404,
            {"error": {"message": "Not found",
                       "type": "invalid_request_error",
                       "code": "not_found"}},
        )

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


def start_stub() -> tuple[ThreadingHTTPServer, str]:
    """Start the stub on an ephemeral localhost port; returns (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubGatewayHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/v1"


if __name__ == "__main__":
    server, base_url = start_stub()
    print(f"Stub Antseed gateway at {base_url} (demo key: {DEMO_KEY})", flush=True)
    print("Press Ctrl-C to stop.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
