"""RationRight — Phase 5: Agent 4 (Alert Generator) tests.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import unittest

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
from agents.agent_4_alert_generator import Agent4AlertGenerator
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset

ALERT_FIELDS = {
    "alert_id",
    "case_id",
    "severity",
    "title",
    "message",
    "recommended_action",
    "status",
}


def real_case():
    """Run the real Agent 1 → 2 → 3 chain to produce a genuine case."""
    dataset = load_dataset(DEFAULT_DATASET_PATH)
    transactions = dataset["transactions"]
    anomalies = Agent1TransactionAnalyst().run(transactions)["anomalies"]
    finding = Agent2AnomalyInvestigator().run(
        {"anomaly": anomalies[0], "transactions": transactions}
    )
    return Agent3EvidenceCaseBuilder().run(
        {"findings": [finding], "transactions": transactions}
    )


def ready_case(case_id="CASE001", severity="high", evidence=None, summary="Summary."):
    """Build a well-formed Agent 3-style case for isolated tests."""
    return {
        "case_id": case_id,
        "severity": severity,
        "status": "requires_human_review",
        "finding_ids": ["FIND001"],
        "summary": summary,
        "evidence": evidence if evidence is not None else [
            {"type": "time_difference", "value": 12.0, "unit": "minutes"},
            {"type": "distance", "value": 1148.09, "unit": "km"},
        ],
        "confidence": 0.9,
        "recommended_action": "Human verification",
    }


class TestAgent4ValidCase(unittest.TestCase):
    """TEST 1 — the REAL Agent 3 case produces a valid review alert."""

    @classmethod
    def setUpClass(cls):
        cls.case = real_case()
        cls.alert = Agent4AlertGenerator().run(cls.case)

    def test_alert_is_generated(self):
        self.assertEqual(set(self.alert.keys()), ALERT_FIELDS)
        self.assertEqual(self.alert["alert_id"], "ALERT001")
        self.assertEqual(self.alert["case_id"], "CASE001")
        self.assertEqual(self.alert["status"], "open")
        self.assertEqual(self.alert["severity"], "high")
        self.assertEqual(self.alert["recommended_action"], "Human verification")
        self.assertTrue(self.alert["title"])
        self.assertTrue(self.alert["message"])

    def test_message_contains_verified_evidence(self):
        message = self.alert["message"]
        self.assertIn("12.0", message)
        self.assertIn("1148.09", message)

    def test_language_is_careful(self):
        text = (self.alert["title"] + " " + self.alert["message"]).lower()
        for banned in ("guilty", "fraud", "block", "deny", "suspend", "punish"):
            self.assertNotIn(banned, text)
        self.assertIn("human verification", text)


class TestAgent4UnverifiedCase(unittest.TestCase):
    """TEST 2 — a not-ready case never produces a normal review alert."""

    def test_not_ready_case_alert(self):
        case = {
            "case_id": "CASE002",
            "severity": "low",
            "status": "not_ready",
            "finding_ids": ["FIND001"],
            "summary": "Case is not ready.",
            "evidence": [],
            "confidence": 0.0,
            "recommended_action": "Human verification",
        }
        alert = Agent4AlertGenerator().run(case)
        self.assertEqual(alert["status"], "not_ready")
        self.assertNotEqual(alert["status"], "open")
        self.assertEqual(alert["severity"], "low")


class TestAgent4MissingEvidence(unittest.TestCase):
    """TEST 3 — missing evidence fails safely with a not-ready alert."""

    def test_missing_evidence_not_ready(self):
        case = ready_case(case_id="CASE003", evidence=[])
        alert = Agent4AlertGenerator().run(case)
        self.assertEqual(alert["status"], "not_ready")
        self.assertEqual(alert["severity"], "low")
        self.assertIn("evidence", alert["message"].lower())

    def test_missing_required_evidence_type_not_ready(self):
        case = ready_case(
            case_id="CASE004",
            evidence=[{"type": "time_difference", "value": 12.0, "unit": "minutes"}],
        )
        alert = Agent4AlertGenerator().run(case)
        self.assertEqual(alert["status"], "not_ready")


class TestAgent4EvidencePreservation(unittest.TestCase):
    """TEST 4 — Agent 3/Agent 2 evidence values are preserved exactly."""

    def test_real_case_values_preserved(self):
        case = real_case()
        alert = Agent4AlertGenerator().run(case)
        for entry in case["evidence"]:
            self.assertIn(str(entry["value"]), alert["message"])
        self.assertEqual(alert["severity"], case["severity"])

    def test_custom_values_preserved(self):
        case = ready_case(
            case_id="CASE005",
            severity="medium",
            evidence=[
                {"type": "time_difference", "value": 25.0, "unit": "minutes"},
                {"type": "distance", "value": 500.5, "unit": "km"},
            ],
        )
        alert = Agent4AlertGenerator().run(case)
        self.assertEqual(alert["severity"], "medium")
        self.assertIn("25.0", alert["message"])
        self.assertIn("500.5", alert["message"])


class TestAgent4NoFabrication(unittest.TestCase):
    """TEST 5 — every alert fact comes from the Agent 3 input."""

    def test_message_contains_only_input_values(self):
        case = real_case()
        alert = Agent4AlertGenerator().run(case)
        # No transaction or beneficiary IDs are guessed into the message.
        self.assertNotIn("TX", alert["message"])
        self.assertNotIn("BEN", alert["message"])
        self.assertIn("Potential anomaly detected", alert["message"])
        for entry in case["evidence"]:
            self.assertIn(str(entry["value"]), alert["message"])


class TestAgent4PriorityRules(unittest.TestCase):
    """TEST 6 — severity/priority follows documented deterministic rules."""

    def test_severity_preserved_for_each_level(self):
        for severity in ("high", "medium", "low"):
            case = ready_case(case_id=f"CASE-{severity}", severity=severity)
            alert = Agent4AlertGenerator().run(case)
            self.assertEqual(alert["severity"], severity)

    def test_invalid_severity_rejected(self):
        case = ready_case(severity="urgent")
        with self.assertRaises(ValueError):
            Agent4AlertGenerator().run(case)


class TestAgent4MissingBeneficiary(unittest.TestCase):
    """TEST 7 — no beneficiary is ever guessed."""

    def test_alert_contains_no_beneficiary_identity(self):
        case = real_case()
        alert = Agent4AlertGenerator().run(case)
        self.assertNotIn("beneficiary_id", alert)
        self.assertNotIn("BEN", alert["message"])
        self.assertNotIn("identity", alert["message"].lower())


class TestAgent4Agent3Compatibility(unittest.TestCase):
    """TEST 8 — Agent 4 consumes actual Agent 3 output without rewriting."""

    def test_consumes_actual_agent_3_output(self):
        case = real_case()
        self.assertEqual(case["status"], "requires_human_review")
        alert = Agent4AlertGenerator().run(case)
        self.assertEqual(alert["status"], "open")
        self.assertEqual(alert["case_id"], case["case_id"])
        self.assertEqual(alert["severity"], case["severity"])


class TestAgent4InvalidInput(unittest.TestCase):
    """Malformed input produces clear validation errors."""

    def test_invalid_input_raises(self):
        generator = Agent4AlertGenerator()
        with self.assertRaises(ValueError):
            generator.run("not-a-case")
        with self.assertRaises(ValueError):
            generator.run({})
        with self.assertRaises(ValueError):
            generator.run(ready_case(case_id="CASE-X", severity="urgent"))
        with self.assertRaises(ValueError):
            generator.run({
                "case_id": "CASE001", "severity": "high", "status": "bogus",
                "finding_ids": ["FIND001"], "summary": "s", "evidence": [],
                "confidence": 0.5, "recommended_action": "Human verification",
            })
        with self.assertRaises(ValueError):
            generator.run({
                "case_id": "CASE001", "severity": "high", "status": "requires_human_review",
                "finding_ids": ["FIND001"], "summary": "s",
                "evidence": [{"type": "time_difference", "value": "abc", "unit": "minutes"}],
                "confidence": 0.5, "recommended_action": "Human verification",
            })
        with self.assertRaises(ValueError):
            generator.run({
                "case_id": "CASE001", "severity": "high", "status": "requires_human_review",
                "finding_ids": ["FIND001"],
                "evidence": [],
                "confidence": 0.5, "recommended_action": "Human verification",
            })


if __name__ == "__main__":
    unittest.main()
