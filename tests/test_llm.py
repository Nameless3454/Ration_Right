"""Phase 10 tests — optional LLM narrative layer.

Covers the ``agents.llm`` module (activation, fail-open behavior, safety
guards) and the agent wiring (Agent 2 explanation, Agent 3 summary, Agent 4
message) with injected generators. The real OpenAI/OpenRouter API is never
called in tests: ``generator`` injection and a mocked ``_chat_completion``
make every path testable deterministically.
"""

import os
import unittest
import urllib.error
from unittest import mock

from agents import llm
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
from agents.agent_4_alert_generator import Agent4AlertGenerator
from scripts.validate_dataset import load_dataset

TX = load_dataset("data/synthetic/transactions.json")["transactions"]

A2_PAYLOAD = {
    "anomaly": {
        "anomaly_id": "ANOM001",
        "anomaly_type": "rapid_geographic_transaction",
        "transaction_ids": ["TX001", "TX002"],
        "beneficiary_id": "BEN001",
        "reason": "Two transactions occurred within a short time interval at distant locations.",
        "severity": "high",
    },
    "transactions": TX,
}

A2_VERIFIED = Agent2AnomalyInvestigator().run(A2_PAYLOAD, finding_id="FIND001")
A3_CASE = Agent3EvidenceCaseBuilder().run({"findings": [A2_VERIFIED], "transactions": TX})
A4_ALERT = Agent4AlertGenerator().run(A3_CASE)


def _enable_llm():
    os.environ["RATIONRIGHT_LLM_ENABLED"] = "1"
    os.environ["OPENAI_API_KEY"] = "sk-test"


class TestLLMModule(unittest.TestCase):
    """Direct tests of agents/llm.py."""

    def tearDown(self):
        for name in ("RATIONRIGHT_LLM_ENABLED", "OPENAI_API_KEY", "RATIONRIGHT_LLM_MODEL",
                     "RATIONRIGHT_LLM_BASE_URL"):
            os.environ.pop(name, None)

    def test_disabled_by_default_returns_fallback(self):
        self.assertFalse(llm.llm_enabled())
        self.assertEqual(
            llm.maybe_generate("agent_3_summary", {"x": 1}, "fallback text"),
            "fallback text",
        )

    def test_enabled_requires_key(self):
        os.environ["RATIONRIGHT_LLM_ENABLED"] = "1"
        self.assertFalse(llm.llm_enabled())
        os.environ["OPENAI_API_KEY"] = "sk-test"
        self.assertTrue(llm.llm_enabled())

    def test_no_network_call_when_disabled(self):
        with mock.patch.object(llm, "_chat_completion") as chat:
            self.assertEqual(
                llm.generate_narrative("agent_3_summary", {"x": 1}, "fallback text"),
                "fallback text",
            )
            chat.assert_not_called()

    def test_unknown_kind_returns_fallback_without_call(self):
        _enable_llm()
        with mock.patch.object(llm, "_chat_completion") as chat:
            self.assertEqual(
                llm.generate_narrative("unknown_kind", {}, "fallback text"),
                "fallback text",
            )
            chat.assert_not_called()

    def test_transport_failure_returns_fallback(self):
        _enable_llm()
        with mock.patch.object(
            llm, "_chat_completion", side_effect=RuntimeError("connection reset")
        ):
            self.assertEqual(
                llm.generate_narrative("agent_3_summary", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_http_error_returns_fallback(self):
        _enable_llm()
        error = urllib.error.HTTPError(
            "https://example.invalid/chat/completions", 401, "Unauthorized", None, None
        )
        with mock.patch.object(llm, "_chat_completion", side_effect=error):
            self.assertEqual(
                llm.generate_narrative("agent_3_summary", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_success_uses_response(self):
        _enable_llm()
        with mock.patch.object(
            llm, "_chat_completion", return_value=" A concise summary of the case. "
        ) as chat:
            result = llm.generate_narrative(
                "agent_3_summary", {"case_id": "CASE001"}, "fallback text"
            )
        self.assertEqual(result, "A concise summary of the case.")
        self.assertEqual(chat.call_count, 1)
        kwargs = chat.call_args.kwargs
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertEqual(kwargs["base_url"], llm.DEFAULT_BASE_URL)
        self.assertEqual(kwargs["model"], llm.DEFAULT_MODEL)
        self.assertEqual(kwargs["timeout"], llm.DEFAULT_TIMEOUT_SECONDS)
        self.assertIn("CASE001", kwargs["user_text"])

    def test_custom_base_url_is_used(self):
        _enable_llm()
        os.environ["RATIONRIGHT_LLM_BASE_URL"] = "https://openrouter.ai/api/v1"
        with mock.patch.object(llm, "_chat_completion", return_value="fine") as chat:
            llm.generate_narrative("agent_3_summary", {}, "fallback text")
        self.assertEqual(
            chat.call_args.kwargs["base_url"], "https://openrouter.ai/api/v1"
        )

    def test_empty_response_returns_fallback(self):
        _enable_llm()
        with mock.patch.object(llm, "_chat_completion", return_value="   "):
            self.assertEqual(
                llm.generate_narrative("agent_4_message", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_non_string_response_returns_fallback(self):
        _enable_llm()
        with mock.patch.object(llm, "_chat_completion", return_value=None):
            self.assertEqual(
                llm.generate_narrative("agent_4_message", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_forbidden_guilt_language_returns_fallback(self):
        _enable_llm()
        with mock.patch.object(
            llm, "_chat_completion", return_value="The beneficiary committed fraud."
        ):
            self.assertEqual(
                llm.generate_narrative("agent_4_message", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_oversized_response_returns_fallback(self):
        _enable_llm()
        with mock.patch.object(
            llm, "_chat_completion", return_value="word " * (llm.MAX_NARRATIVE_CHARS + 50)
        ):
            self.assertEqual(
                llm.generate_narrative("agent_3_summary", {"x": 1}, "fallback text"),
                "fallback text",
            )

    def test_generator_raising_returns_fallback(self):
        def boom(kind, context, fallback):
            raise RuntimeError("LLM exploded")

        self.assertEqual(
            llm.maybe_generate("agent_3_summary", {}, "fallback text", generator=boom),
            "fallback text",
        )

    def test_generator_returning_garbage_returns_fallback(self):
        self.assertEqual(
            llm.maybe_generate("agent_3_summary", {}, "fallback text", generator=lambda k, c, f: 42),
            "fallback text",
        )

    def test_explicit_generator_honored_when_llm_disabled(self):
        # Dependency injection is opt-in by the caller, not env-gated.
        self.assertEqual(
            llm.maybe_generate("agent_3_summary", {}, "fallback", generator=lambda k, c, f: "custom"),
            "custom",
        )


class TestAgentWiring(unittest.TestCase):
    """Injected generators must replace narratives but never structured fields."""

    def test_agent_2_explanation_replaced_evidence_untouched(self):
        generator = mock.MagicMock(return_value="LLM explanation of the verified anomaly.")
        finding = Agent2AnomalyInvestigator(narrative_generator=generator).run(
            A2_PAYLOAD, finding_id="FIND001"
        )
        self.assertEqual(finding["explanation"], "LLM explanation of the verified anomaly.")
        self.assertEqual(
            finding["evidence"],
            {"time_difference_minutes": 12.0, "distance_km": 1148.09},
        )
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["transaction_ids"], ["TX001", "TX002"])
        self.assertEqual(finding["anomaly_id"], "ANOM001")
        generator.assert_called_once()
        kind, context, _ = generator.call_args[0]
        self.assertEqual(kind, "agent_2_explanation")
        self.assertEqual(context["time_difference_minutes"], 12.0)
        self.assertEqual(context["distance_km"], 1148.09)

    def test_agent_2_generator_failure_falls_back(self):
        def boom(kind, context, fallback):
            raise RuntimeError("LLM down")

        finding = Agent2AnomalyInvestigator(narrative_generator=boom).run(
            A2_PAYLOAD, finding_id="FIND001"
        )
        self.assertIn("12.00 minutes apart", finding["explanation"])
        self.assertEqual(finding["evidence"]["distance_km"], 1148.09)

    def test_agent_3_summary_replaced_evidence_untouched(self):
        generator = mock.MagicMock(return_value="LLM case summary for review.")
        case = Agent3EvidenceCaseBuilder(narrative_generator=generator).run(
            {"findings": [A2_VERIFIED], "transactions": TX}
        )
        self.assertEqual(case["summary"], "LLM case summary for review.")
        self.assertEqual(case["status"], "requires_human_review")
        self.assertEqual(case["severity"], "high")
        self.assertEqual(case["confidence"], 0.9)
        self.assertEqual(case["finding_ids"], ["FIND001"])
        self.assertEqual(
            case["evidence"],
            [
                {"type": "time_difference", "value": 12.0, "unit": "minutes"},
                {"type": "distance", "value": 1148.09, "unit": "km"},
            ],
        )
        kind, context, _ = generator.call_args[0]
        self.assertEqual(kind, "agent_3_summary")
        self.assertEqual(context["transaction_ids"], ["TX001", "TX002"])
        self.assertEqual(context["beneficiaries"], ["BEN001"])

    def test_agent_3_generator_failure_falls_back(self):
        def boom(kind, context, fallback):
            raise RuntimeError("LLM down")

        case = Agent3EvidenceCaseBuilder(narrative_generator=boom).run(
            {"findings": [A2_VERIFIED], "transactions": TX}
        )
        self.assertIn("TX001", case["summary"])
        self.assertIn("12.00 minutes apart", case["summary"])
        self.assertEqual(case["evidence"][1]["value"], 1148.09)

    def test_agent_4_message_replaced_evidence_untouched(self):
        generator = mock.MagicMock(return_value="LLM alert message for the reviewer.")
        alert = Agent4AlertGenerator(narrative_generator=generator).run(A3_CASE)
        self.assertEqual(alert["message"], "LLM alert message for the reviewer.")
        self.assertEqual(alert["status"], "open")
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["case_id"], "CASE001")
        self.assertEqual(alert["recommended_action"], "Human verification")
        kind, context, _ = generator.call_args[0]
        self.assertEqual(kind, "agent_4_message")
        self.assertEqual(context["case_id"], "CASE001")

    def test_agent_4_generator_failure_falls_back(self):
        def boom(kind, context, fallback):
            raise RuntimeError("LLM down")

        alert = Agent4AlertGenerator(narrative_generator=boom).run(A3_CASE)
        self.assertIn("1148.09 km apart", alert["message"])
        self.assertEqual(alert["status"], "open")

    def test_default_path_unchanged_without_env(self):
        # Without env vars, no generator is invoked and deterministic text is used.
        self.assertNotIn("RATIONRIGHT_LLM_ENABLED", os.environ)
        finding = Agent2AnomalyInvestigator().run(A2_PAYLOAD, finding_id="FIND001")
        self.assertIn("12.00 minutes apart", finding["explanation"])
        case = Agent3EvidenceCaseBuilder().run({"findings": [A2_VERIFIED], "transactions": TX})
        self.assertIn("12.00 minutes apart", case["summary"])
        alert = Agent4AlertGenerator().run(A3_CASE)
        self.assertIn("12.0 minutes apart", alert["message"])

    def test_agent_4_llm_generation_never_touches_evidence_field(self):
        # Phase 9 guard: the Alert schema has no evidence field, so there is
        # nothing for the LLM to overwrite; the message is the only narrative.
        generator = mock.MagicMock(return_value="Custom alert text.")
        alert = Agent4AlertGenerator(narrative_generator=generator).run(A3_CASE)
        self.assertEqual(set(alert.keys()), {
            "alert_id", "case_id", "severity", "title", "message",
            "recommended_action", "status",
        })


if __name__ == "__main__":
    unittest.main()
