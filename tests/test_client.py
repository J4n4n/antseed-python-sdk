"""Tests for the Antseed demo SDK.

Verification status (see README for the full note):

* LIVE against a real gateway: NOTHING — Antseed has no hosted public
  gateway; every user runs their own (``http://localhost:8379/v1``), and
  starting one needs the node software plus a funded wallet. No key was
  bought and no money was spent.
* VERIFIED over real HTTP against the stub gateway
  (``tests/stub_gateway.py``): every test below. The stub answers with
  fixtures shaped from the real gateway's own code and docs, so what is
  verified is the client's wire behaviour — request shape, auth header,
  response parsing, cost math, and error mapping — not the live network.

Run:  ``python -m unittest discover -s tests -v``
"""

from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stub_gateway import DEMO_KEY, StubGatewayHandler, start_stub  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from antseed import (  # noqa: E402
    AntseedClient,
    AuthenticationError,
    NotFoundError,
    ProviderUnavailableError,
    pin_model,
)
from antseed.models import Usage  # noqa: E402


class StubCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base_url = start_stub()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        StubGatewayHandler.requests.clear()
        self.client = AntseedClient(
            api_key=DEMO_KEY, base_url=self.base_url
        )

    def last_request(self):
        return StubGatewayHandler.requests[-1]


class TestConfig(unittest.TestCase):
    def test_missing_key_raises(self):
        os.environ.pop("ANTSEED_API_KEY", None)
        with self.assertRaises(ValueError):
            AntseedClient(api_key=None, base_url="http://localhost:8379/v1")

    def test_base_url_normalisation(self):
        client = AntseedClient(api_key=DEMO_KEY, base_url="http://localhost:8379")
        self.assertEqual(client.base_url, "http://localhost:8379/v1")
        client = AntseedClient(api_key=DEMO_KEY, base_url="https://gw.example.com/v1/")
        self.assertEqual(client.base_url, "https://gw.example.com/v1")

    def test_pin_model(self):
        self.assertEqual(
            pin_model("AB" * 20, "deepseek-v4-flash"),
            f"{'ab' * 20}@deepseek-v4-flash",
        )
        self.assertEqual(pin_model("0x" + "ab" * 20, "m"), f"{'ab' * 20}@m")


class TestListModels(StubCase):
    def test_lists_models_with_peers_and_pricing(self):
        models = self.client.list_models()
        self.assertEqual(len(models), 2)
        deepseek = next(m for m in models if m.id == "deepseek-v4-flash")
        self.assertEqual(deepseek.type, "text")
        self.assertEqual(deepseek.context_length, 131072)
        self.assertEqual(deepseek.aliases, ["deepseek-flash"])
        self.assertEqual(len(deepseek.peers), 2)
        self.assertEqual(deepseek.capability_coverage.tool_use, 2)

    def test_auth_header_sent(self):
        self.client.list_models()
        self.assertEqual(
            self.last_request()["headers"].get("Authorization"),
            f"Bearer {DEMO_KEY}",
        )

    def test_type_filter_is_passed_through(self):
        routers = self.client.list_models(type="router")
        self.assertEqual(len(routers), 1)
        self.assertEqual(routers[0].type, "router")
        self.assertEqual(
            routers[0].peers[0].model,
            "d" * 40 + "@irp-suggest",
        )
        self.assertEqual(routers[0].peers[0].price_usd_per_request, 0.001)
        self.assertEqual(self.last_request()["query"], {"type": ["router"]})

    def test_cheapest_peer_and_free_offer(self):
        models = self.client.list_models()
        deepseek = next(m for m in models if m.id == "deepseek-v4-flash")
        cheapest = deepseek.cheapest_peer()
        self.assertIsNotNone(cheapest)
        assert cheapest is not None
        self.assertEqual(cheapest.display_name, "Peer Two")
        self.assertEqual(cheapest.input_usd_per_million, 1)
        free = next(m for m in models if m.id == "free-model")
        self.assertTrue(free.peers[0].is_free)

    def test_estimate_cost_math(self):
        models = self.client.list_models()
        deepseek = next(m for m in models if m.id == "deepseek-v4-flash")
        usage = Usage(
            prompt_tokens=1000, completion_tokens=100,
            total_tokens=1100, cached_input_tokens=200,
        )
        # Cheapest peer (Peer Two): in $1/M, cached $0.5/M, out $5/M.
        # (1000-200)*1 + 200*0.5 + 100*5 = 800 + 100 + 500 = 1400 / 1e6.
        cost = deepseek.estimate_cost(usage)
        self.assertEqual(cost, Decimal("0.0014"))
        # Pinned to Peer One: in $2/M, out $10/M, no cached rate (falls
        # back to the input rate): 800*2 + 200*2 + 100*10 = 3000 / 1e6.
        cost_pinned = deepseek.estimate_cost(usage, peer_id="aa" * 20)
        self.assertEqual(cost_pinned, Decimal("0.003"))
        # Free model: zero cost.
        free = next(m for m in models if m.id == "free-model")
        self.assertEqual(free.estimate_cost(usage), Decimal("0"))


class TestChatCompletion(StubCase):
    def test_text_usage_and_gateway_tag(self):
        reply = self.client.chat_completion(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertEqual(reply.text, "Hello from the stub gateway.")
        self.assertEqual(reply.model, "deepseek-v4-flash")
        self.assertEqual(reply.finish_reason, "stop")
        self.assertEqual(reply.usage.prompt_tokens, 1000)
        self.assertEqual(reply.usage.completion_tokens, 100)
        self.assertEqual(reply.usage.total_tokens, 1100)
        self.assertEqual(reply.usage.cached_input_tokens, 200)
        self.assertEqual(reply.gateway_tag, "req_demo")

    def test_request_body_shape(self):
        self.client.chat_completion(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=256,
            routing={"cost_quality_tradeoff": 7},
            user="end-user-1",
            end_user="customer-42",
        )
        req = self.last_request()
        self.assertEqual(req["path"], "/v1/chat/completions")
        self.assertEqual(req["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(req["body"]["messages"], [{"role": "user", "content": "Hi"}])
        self.assertEqual(req["body"]["temperature"], 0.7)
        self.assertEqual(req["body"]["max_tokens"], 256)
        self.assertEqual(req["body"]["routing"], {"cost_quality_tradeoff": 7})
        self.assertEqual(req["body"]["user"], "end-user-1")
        # Header names arrive capitalised over HTTP; compare case-insensitively.
        lowered = {k.lower(): v for k, v in req["headers"].items()}
        self.assertEqual(lowered.get("x-antseed-end-user"), "customer-42")

    def test_cost_via_client(self):
        models = self.client.list_models()
        deepseek = next(m for m in models if m.id == "deepseek-v4-flash")
        reply = self.client.chat_completion(
            model="deepseek-v4-flash",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertEqual(
            self.client.estimate_cost(deepseek, reply.usage),
            Decimal("0.0014"),
        )

    def test_provider_unavailable_maps_to_502_error(self):
        with self.assertRaises(ProviderUnavailableError) as ctx:
            self.client.chat_completion(
                model="missing-model",
                messages=[{"role": "user", "content": "Hello"}],
            )
        self.assertEqual(ctx.exception.status, 502)


class TestKeyUsage(StubCase):
    def test_key_usage_and_limits(self):
        key = self.client.get_key_usage()
        self.assertEqual(key.label, "Demo")
        self.assertEqual(key.requests, 42)
        self.assertEqual(key.spent_usd, Decimal("1.204310"))
        self.assertEqual(key.topped_up_usd, Decimal("0"))
        self.assertEqual(key.input_tokens, 180233)
        self.assertEqual(key.cached_input_tokens, 90112)
        self.assertEqual(key.output_tokens, 20118)
        self.assertEqual(key.limits["daily"].limit_usd, Decimal("2"))
        self.assertEqual(key.limits["daily"].remaining_usd, Decimal("1.59"))
        self.assertIsNone(key.limits["weekly"].limit_usd)
        self.assertFalse(key.topup_enabled)


class TestErrors(StubCase):
    def test_bad_key_is_401(self):
        bad = AntseedClient(api_key="antseed_wrong", base_url=self.base_url)
        with self.assertRaises(AuthenticationError) as ctx:
            bad.list_models()
        self.assertEqual(ctx.exception.status, 401)
        self.assertEqual(ctx.exception.code, "invalid_api_key")

    def test_unknown_path_is_404(self):
        with self.assertRaises(NotFoundError):
            self.client._get_json("/nope")


if __name__ == "__main__":
    unittest.main()
