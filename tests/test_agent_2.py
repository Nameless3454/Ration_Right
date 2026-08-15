"""RationRight — Phase 3: Agent 2 (Anomaly Investigator) tests.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import unittest

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from scripts.validate_dataset import DEFAULT_DATASET_PATH, haversine_km, load_dataset

FINDING_FIELDS = {
    "finding_id",
    "anomaly_id",
    "status",
    "transaction_ids",
    "evidence",
    "evidence_sources",
    "explanation",
}


def make_tx(transaction_id, beneficiary_id, timestamp, latitude, longitude,
            ration_type="rice", quantity=10):
    """Build a contract-compliant synthetic transaction record."""
    return {
        "transaction_id": transaction_id,
        "beneficiary_id": beneficiary_id,
        "timestamp": timestamp,
        "latitude": latitude,
        "longitude": longitude,
        "ration_type": ration_type,
        "quantity": quantity,
    }


def candidate(anomaly_id="ANOM001", transaction_ids=("TX001", "TX002"),
              beneficiary_id="BEN001", severity="high",
              reason="Two transactions occurred within a short time interval at distant locations."):
    """Build an Agent 1-style anomaly candidate."""
    return {
        "anomaly_id": anomaly_id,
        "anomaly_type": "rapid_geographic_transaction",
        "transaction_ids": list(transaction_ids),
        "beneficiary_id": beneficiary_id,
        "reason": reason,
        "severity": severity,
    }


class TestAgent2ValidCandidate(unittest.TestCase):
    """TEST 1 — the real planted anomaly is verified with calculated evidence."""

    @classmethod
    def setUpClass(cls):
        cls.transactions = load_dataset(DEFAULT_DATASET_PATH)["transactions"]
        cls.finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(),
            "transactions": cls.transactions,
        })

    def test_status_verified(self):
        self.assertEqual(self.finding["status"], "verified")

    def test_evidence_contains_actual_calculations(self):
        self.assertEqual(self.finding["evidence"]["time_difference_minutes"], 12.0)
        self.assertAlmostEqual(self.finding["evidence"]["distance_km"], 1148.09, places=2)

    def test_contract_fields(self):
        self.assertEqual(set(self.finding.keys()), FINDING_FIELDS)
        self.assertEqual(self.finding["anomaly_id"], "ANOM001")
        self.assertEqual(self.finding["transaction_ids"], ["TX001", "TX002"])
        self.assertEqual(self.finding["evidence_sources"], ["TX001", "TX002"])
        self.assertTrue(self.finding["explanation"])

    def test_evidence_is_calculated_not_a_template(self):
        """Different input data must produce different calculated evidence."""
        transactions = [
            make_tx("TX900", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX901", "BEN900", "2026-08-01T10:25:00", 23.0225, 72.5714),
        ]
        anomaly = candidate(anomaly_id="ANOM900", transaction_ids=("TX900", "TX901"),
                            beneficiary_id="BEN900", reason="test")
        finding = Agent2AnomalyInvestigator().run({"anomaly": anomaly, "transactions": transactions})
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["evidence"]["time_difference_minutes"], 25.0)
        expected_distance = haversine_km(19.0760, 72.8777, 23.0225, 72.5714)
        self.assertAlmostEqual(finding["evidence"]["distance_km"], expected_distance, places=2)

    def test_explanation_avoids_guilt_language(self):
        text = self.finding["explanation"].lower()
        self.assertNotIn("guilty", text)
        self.assertNotIn("fraud", text)
        self.assertNotIn("committed", text)
        self.assertIn("human verification", text)


class TestAgent2MissingTransaction(unittest.TestCase):
    """TEST 2 — a missing transaction cannot be verified and invents nothing."""

    def test_one_transaction_missing(self):
        transactions = [make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(transaction_ids=("TX001", "TX999")),
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertEqual(finding["evidence"], {})
        self.assertEqual(finding["evidence_sources"], [])
        self.assertIn("TX999", finding["explanation"])

    def test_empty_transaction_list(self):
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(),
            "transactions": [],
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertEqual(finding["evidence"], {})


class TestAgent2MissingData(unittest.TestCase):
    """TEST 3/4/5 — missing or invalid data prevents the relevant calculation."""

    def _run_with(self, tx_a, tx_b):
        return Agent2AnomalyInvestigator().run({
            "anomaly": candidate(transaction_ids=("TX001", "TX002")),
            "transactions": [tx_a, tx_b],
        })

    def test_missing_timestamp(self):
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)
        tx_b = {"transaction_id": "TX002", "beneficiary_id": "BEN001",
                "latitude": 28.6139, "longitude": 77.2090,
                "ration_type": "rice", "quantity": 10}
        finding = self._run_with(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")
        self.assertEqual(finding["evidence"], {})
        self.assertIn("timestamp", finding["explanation"].lower())

    def test_invalid_timestamp(self):
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)
        tx_b = make_tx("TX002", "BEN001", "not-a-timestamp", 28.6139, 77.2090)
        finding = self._run_with(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")
        self.assertIn("timestamp", finding["explanation"].lower())

    def test_missing_coordinates(self):
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)
        tx_b = {"transaction_id": "TX002", "beneficiary_id": "BEN001",
                "timestamp": "2026-08-01T10:12:00",
                "ration_type": "rice", "quantity": 10}
        finding = self._run_with(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")
        self.assertEqual(finding["evidence"], {})
        self.assertIn("coordinate", finding["explanation"].lower())

    def test_invalid_coordinates(self):
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777)
        tx_b = make_tx("TX002", "BEN001", "2026-08-01T10:12:00", 95.0, 77.2090)
        finding = self._run_with(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")
        self.assertIn("coordinate", finding["explanation"].lower())


class TestAgent2WrongBeneficiary(unittest.TestCase):
    """TEST 6 — a same-beneficiary anomaly must never be force-verified."""

    def test_referenced_transactions_belong_to_different_beneficiaries(self):
        transactions = [
            make_tx("TX001", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX002", "BEN901", "2026-08-01T10:12:00", 28.6139, 77.2090),
        ]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(),
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertIn("beneficiar", finding["explanation"].lower())

    def test_beneficiary_mismatch_with_expected(self):
        transactions = [
            make_tx("TX001", "BEN901", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX002", "BEN901", "2026-08-01T10:12:00", 28.6139, 77.2090),
        ]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(beneficiary_id="BEN900"),
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertIn("BEN901", finding["explanation"])


class TestAgent2NormalTransactions(unittest.TestCase):
    """TEST 7 — transactions that do not satisfy the thresholds stay unverified."""

    def test_distance_below_threshold(self):
        transactions = [
            make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX002", "BEN001", "2026-08-01T10:12:00", 19.0800, 72.8800),
        ]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(),
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertEqual(finding["evidence"], {})
        self.assertIn("threshold", finding["explanation"].lower())

    def test_interval_above_threshold(self):
        transactions = [
            make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 19.0760, 72.8777),
            make_tx("TX002", "BEN001", "2026-08-03T09:00:00", 28.6139, 77.2090),
        ]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": candidate(),
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "unverified")
        self.assertIn("threshold", finding["explanation"].lower())


class TestAgent2Boundary(unittest.TestCase):
    """TEST 8 — behavior around the configured thresholds is deterministic."""

    def _verify(self, tx_a, tx_b):
        return Agent2AnomalyInvestigator().run({
            "anomaly": candidate(transaction_ids=("TX001", "TX002")),
            "transactions": [tx_a, tx_b],
        })

    def test_interval_at_threshold_and_distance_just_above(self):
        # Exactly 60 minutes and ~100.08 km: both inclusive bounds hold.
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 0.0, 0.0)
        tx_b = make_tx("TX002", "BEN001", "2026-08-01T11:00:00", 0.9, 0.0)
        finding = self._verify(tx_a, tx_b)
        self.assertEqual(finding["status"], "verified")

    def test_distance_just_below_threshold(self):
        # ~99.96 km: just under the 100 km inclusive bound.
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 0.0, 0.0)
        tx_b = make_tx("TX002", "BEN001", "2026-08-01T11:00:00", 0.899, 0.0)
        finding = self._verify(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")

    def test_interval_just_above_threshold(self):
        # 60.02 minutes: just over the 60 min inclusive bound.
        tx_a = make_tx("TX001", "BEN001", "2026-08-01T10:00:00", 0.0, 0.0)
        tx_b = make_tx("TX002", "BEN001", "2026-08-01T11:00:01", 2.0, 0.0)
        finding = self._verify(tx_a, tx_b)
        self.assertEqual(finding["status"], "unverified")


class TestAgent2Agent1Compatibility(unittest.TestCase):
    """TEST 9 — Agent 2 consumes real Agent 1 output without rewriting."""

    def test_consumes_actual_agent_1_output(self):
        dataset = load_dataset(DEFAULT_DATASET_PATH)
        transactions = dataset["transactions"]
        agent1_result = Agent1TransactionAnalyst().run(transactions)
        self.assertGreaterEqual(len(agent1_result["anomalies"]), 1)

        anomaly = agent1_result["anomalies"][0]
        finding = Agent2AnomalyInvestigator().run({
            "anomaly": anomaly,
            "transactions": transactions,
        })
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["anomaly_id"], anomaly["anomaly_id"])
        self.assertEqual(finding["transaction_ids"], anomaly["transaction_ids"])
        self.assertEqual(finding["evidence"]["time_difference_minutes"], 12.0)
        self.assertAlmostEqual(finding["evidence"]["distance_km"], 1148.09, places=2)


class TestAgent2InvalidCandidate(unittest.TestCase):
    """Malformed candidates and payloads are rejected safely."""

    def test_malformed_candidate_raises(self):
        investigator = Agent2AnomalyInvestigator()
        with self.assertRaises(ValueError):
            investigator.run({"anomaly": {"transaction_ids": ["TX001"]}, "transactions": []})
        with self.assertRaises(ValueError):
            investigator.run({"anomaly": {"anomaly_id": "ANOM001", "transaction_ids": "TX001"}, "transactions": []})
        with self.assertRaises(ValueError):
            investigator.run({"anomaly": {"anomaly_id": "ANOM001", "transaction_ids": ["TX001", 42]}, "transactions": []})
        with self.assertRaises(ValueError):
            investigator.run({"anomaly": "not-a-dict", "transactions": []})
        with self.assertRaises(ValueError):
            investigator.run("not-a-payload")


if __name__ == "__main__":
    unittest.main()
