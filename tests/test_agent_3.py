"""RationRight — Phase 4: Agent 3 (Evidence Case Builder) tests.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import re
import unittest

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset

CASE_FIELDS = {
    "case_id",
    "severity",
    "status",
    "finding_ids",
    "summary",
    "evidence",
    "confidence",
    "recommended_action",
}


def make_tx(transaction_id, beneficiary_id, timestamp, latitude, longitude,
            ration_type="rice", quantity=10):
    return {
        "transaction_id": transaction_id,
        "beneficiary_id": beneficiary_id,
        "timestamp": timestamp,
        "latitude": latitude,
        "longitude": longitude,
        "ration_type": ration_type,
        "quantity": quantity,
    }


def make_finding(finding_id="FIND001", anomaly_id="ANOM001", status="verified",
                 transaction_ids=("TX001", "TX002"), evidence=None, evidence_sources=None,
                 explanation="test explanation"):
    return {
        "finding_id": finding_id,
        "anomaly_id": anomaly_id,
        "status": status,
        "transaction_ids": list(transaction_ids),
        "evidence": evidence if evidence is not None
                    else {"time_difference_minutes": 12.0, "distance_km": 1148.09},
        "evidence_sources": list(evidence_sources)
                            if evidence_sources is not None else list(transaction_ids),
        "explanation": explanation,
    }


def real_finding():
    """Run the real Agent 1 + Agent 2 chain to produce a genuine finding."""
    dataset = load_dataset(DEFAULT_DATASET_PATH)
    transactions = dataset["transactions"]
    anomalies = Agent1TransactionAnalyst().run(transactions)["anomalies"]
    finding = Agent2AnomalyInvestigator().run(
        {"anomaly": anomalies[0], "transactions": transactions}
    )
    return finding, transactions


class TestAgent3VerifiedFinding(unittest.TestCase):
    """TEST 1 — a real verified finding produces a structured case."""

    @classmethod
    def setUpClass(cls):
        cls.finding, cls.transactions = real_finding()
        cls.case = Agent3EvidenceCaseBuilder().run(
            {"findings": [cls.finding], "transactions": cls.transactions}
        )

    def test_case_is_created(self):
        self.assertEqual(set(self.case.keys()), CASE_FIELDS)
        self.assertEqual(self.case["case_id"], "CASE001")
        self.assertEqual(self.case["status"], "requires_human_review")
        self.assertEqual(self.case["finding_ids"], ["FIND001"])

    def test_evidence_entries(self):
        entries = {e["type"]: e for e in self.case["evidence"]}
        self.assertEqual(entries["time_difference"]["value"], 12.0)
        self.assertEqual(entries["time_difference"]["unit"], "minutes")
        self.assertEqual(entries["distance"]["value"], 1148.09)
        self.assertEqual(entries["distance"]["unit"], "km")

    def test_severity_confidence_recommendation(self):
        self.assertEqual(self.case["severity"], "high")
        self.assertEqual(self.case["confidence"], 0.9)
        self.assertEqual(self.case["recommended_action"], "Human verification")

    def test_summary_is_factual_and_traceable(self):
        summary = self.case["summary"]
        self.assertIn("TX001", summary)
        self.assertIn("TX002", summary)
        self.assertIn("BEN001", summary)
        lowered = summary.lower()
        self.assertNotIn("guilty", lowered)
        self.assertNotIn("fraud", lowered)
        self.assertIn("human review", lowered)


class TestAgent3Unverified(unittest.TestCase):
    """TEST 2 — an unverified finding is never presented as a verified case."""

    def test_unverified_finding_is_not_ready(self):
        finding = make_finding(status="unverified", evidence={}, evidence_sources=[])
        case = Agent3EvidenceCaseBuilder().run({"findings": [finding], "transactions": []})
        self.assertEqual(case["status"], "not_ready")
        self.assertEqual(case["evidence"], [])
        self.assertEqual(case["confidence"], 0.0)
        self.assertIn("unverified", case["summary"].lower())


class TestAgent3MissingTransaction(unittest.TestCase):
    """TEST 3 — a missing referenced transaction is reported, not invented."""

    def test_missing_referenced_transaction(self):
        finding = make_finding(transaction_ids=("TX001", "TX999"))
        transactions = [make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)]
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [finding], "transactions": transactions}
        )
        self.assertEqual(case["status"], "not_ready")
        self.assertIn("TX999", case["summary"])


class TestAgent3MissingEvidence(unittest.TestCase):
    """TEST 4 — a verified finding without evidence is marked not ready."""

    def test_missing_evidence_not_ready(self):
        finding = make_finding(evidence={}, evidence_sources=[])
        case = Agent3EvidenceCaseBuilder().run({"findings": [finding], "transactions": []})
        self.assertEqual(case["status"], "not_ready")
        self.assertIn("evidence", case["summary"].lower())


class TestAgent3EvidenceConsistency(unittest.TestCase):
    """TEST 5 — Agent 2's numerical evidence is preserved unchanged."""

    def test_case_preserves_agent_2_values_exactly(self):
        finding, transactions = real_finding()
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [finding], "transactions": transactions}
        )
        values = {e["type"]: e["value"] for e in case["evidence"]}
        self.assertEqual(values["time_difference"], finding["evidence"]["time_difference_minutes"])
        self.assertEqual(values["distance"], finding["evidence"]["distance_km"])


class TestAgent3NoFabrication(unittest.TestCase):
    """TEST 6 — every fact in the case exists in the supplied input."""

    def test_summary_facts_come_from_input(self):
        finding, transactions = real_finding()
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [finding], "transactions": transactions}
        )
        summary_ids = set(re.findall(r"TX\d{3}", case["summary"]))
        self.assertTrue(summary_ids.issubset(set(finding["transaction_ids"])))
        summary_beneficiaries = set(re.findall(r"BEN\d{3}", case["summary"]))
        real_beneficiaries = {t["beneficiary_id"] for t in transactions}
        self.assertTrue(summary_beneficiaries.issubset(real_beneficiaries))


class TestAgent3MultipleFindings(unittest.TestCase):
    """TEST 7 — multiple findings are aggregated without mixing evidence."""

    def test_evidence_from_multiple_findings_stays_separate(self):
        finding_a = make_finding("FIND001", "ANOM001", transaction_ids=("TX001", "TX002"),
                                 evidence={"time_difference_minutes": 12.0, "distance_km": 1148.09})
        finding_b = make_finding("FIND002", "ANOM002", transaction_ids=("TX010", "TX011"),
                                 evidence={"time_difference_minutes": 25.0, "distance_km": 500.5})
        transactions = [
            make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX002", "BEN001", "2026-08-01T10:12:00", 28.6139, 77.2090),
            make_tx("TX010", "BEN003", "2026-08-03T09:00:00", 28.6139, 77.2090),
            make_tx("TX011", "BEN003", "2026-08-03T09:25:00", 19.0760, 72.8777),
        ]
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [finding_a, finding_b], "transactions": transactions}
        )
        self.assertEqual(case["status"], "requires_human_review")
        self.assertEqual(case["finding_ids"], ["FIND001", "FIND002"])
        values = [e["value"] for e in case["evidence"]]
        self.assertEqual(values, [12.0, 1148.09, 25.0, 500.5])


class TestAgent3Agent2Compatibility(unittest.TestCase):
    """TEST 8 — Agent 3 consumes actual Agent 2 output without rewriting."""

    def test_consumes_actual_agent_2_output(self):
        finding, transactions = real_finding()
        self.assertEqual(finding["status"], "verified")
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [finding], "transactions": transactions}
        )
        self.assertEqual(case["status"], "requires_human_review")
        self.assertEqual(case["finding_ids"], [finding["finding_id"]])

    def test_single_finding_input_shape(self):
        finding, transactions = real_finding()
        case = Agent3EvidenceCaseBuilder().run(
            {"finding": finding, "transactions": transactions}
        )
        self.assertEqual(case["status"], "requires_human_review")


class TestAgent3InvalidInput(unittest.TestCase):
    """Malformed input produces clear validation errors."""

    def test_invalid_input_raises(self):
        builder = Agent3EvidenceCaseBuilder()
        with self.assertRaises(ValueError):
            builder.run("not-a-payload")
        with self.assertRaises(ValueError):
            builder.run({})
        with self.assertRaises(ValueError):
            builder.run({"findings": []})
        with self.assertRaises(ValueError):
            builder.run({"findings": ["not-a-dict"]})
        with self.assertRaises(ValueError):
            builder.run({"findings": [make_finding(status="bogus")]})
        with self.assertRaises(ValueError):
            builder.run({"findings": [make_finding(evidence={"time_difference_minutes": "abc", "distance_km": 1})]})


if __name__ == "__main__":
    unittest.main()
