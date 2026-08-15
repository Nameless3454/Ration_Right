"""RationRight — Phase 2: Agent 1 (Transaction Analyst) tests.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import unittest

from agents.agent_1_transaction_analyst import (
    ANOMALY_TYPE,
    Agent1TransactionAnalyst,
)
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset

CANDIDATE_FIELDS = {
    "anomaly_id",
    "anomaly_type",
    "transaction_ids",
    "beneficiary_id",
    "reason",
    "severity",
}


def tx(transaction_id, beneficiary_id, timestamp, latitude, longitude,
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


class TestAgent1PlantedAnomaly(unittest.TestCase):
    """TEST 1 — the real Phase 1 planted anomaly is detected from the data."""

    @classmethod
    def setUpClass(cls):
        cls.dataset = load_dataset(DEFAULT_DATASET_PATH)
        cls.anomalies = Agent1TransactionAnalyst().run(cls.dataset["transactions"])["anomalies"]

    def test_planted_pattern_is_detected(self):
        self.assertGreaterEqual(len(self.anomalies), 1)

    def test_planted_pair_is_flagged(self):
        flagged = {tuple(a["transaction_ids"]) for a in self.anomalies}
        self.assertIn(("TX001", "TX002"), flagged)

    def test_ids_come_from_real_dataset(self):
        real_ids = {t["transaction_id"] for t in self.dataset["transactions"]}
        for anomaly in self.anomalies:
            with self.subTest(anomaly=anomaly["anomaly_id"]):
                self.assertTrue(set(anomaly["transaction_ids"]).issubset(real_ids))

    def test_candidate_fields_match_contract_exactly(self):
        for anomaly in self.anomalies:
            with self.subTest(anomaly=anomaly["anomaly_id"]):
                self.assertEqual(set(anomaly.keys()), CANDIDATE_FIELDS, anomaly)

    def test_planted_candidate_values(self):
        anomaly = next(
            a for a in self.anomalies if tuple(a["transaction_ids"]) == ("TX001", "TX002")
        )
        self.assertEqual(anomaly["anomaly_type"], ANOMALY_TYPE)
        self.assertEqual(anomaly["beneficiary_id"], "BEN001")
        self.assertEqual(anomaly["severity"], "high")
        self.assertTrue(anomaly["reason"])

    def test_pattern_detected_even_if_ids_change(self):
        """The agent detects the PATTERN, not hard-coded IDs."""
        transactions = [dict(t) for t in self.dataset["transactions"]]
        transactions[0]["transaction_id"] = "ZZ001"
        transactions[1]["transaction_id"] = "ZZ002"
        anomalies = Agent1TransactionAnalyst().run(transactions)["anomalies"]
        flagged = {tuple(a["transaction_ids"]) for a in anomalies}
        self.assertIn(("ZZ001", "ZZ002"), flagged)


class TestAgent1NormalData(unittest.TestCase):
    """TEST 2 — normal data produces no false high-risk anomaly."""

    def test_real_dataset_without_planted_pair_has_no_anomalies(self):
        dataset = load_dataset(DEFAULT_DATASET_PATH)
        transactions = [
            t for t in dataset["transactions"] if t["transaction_id"] not in ("TX001", "TX002")
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_plain_normal_records_have_no_anomalies(self):
        transactions = [
            tx("TX100", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX101", "BEN900", "2026-08-01T10:30:00", 19.0800, 72.8800),
            tx("TX102", "BEN900", "2026-08-03T09:00:00", 19.0760, 72.8777),
            tx("TX103", "BEN901", "2026-08-01T11:00:00", 12.9716, 77.5946),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})


class TestAgent1BeneficiaryIsolation(unittest.TestCase):
    """TEST 3 — transactions from different beneficiaries are never compared."""

    def test_cross_beneficiary_near_simultaneous_far_apart_is_not_flagged(self):
        transactions = [
            tx("TX200", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),  # Mumbai
            tx("TX201", "BEN901", "2026-08-01T10:05:00", 28.6139, 77.2090),  # Delhi
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_same_beneficiary_short_and_far_is_flagged(self):
        transactions = [
            tx("TX202", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX203", "BEN900", "2026-08-01T10:05:00", 28.6139, 77.2090),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["anomalies"][0]["beneficiary_id"], "BEN900")
        self.assertEqual(result["anomalies"][0]["transaction_ids"], ["TX202", "TX203"])


class TestAgent1MissingData(unittest.TestCase):
    """TEST 4/5 — missing/invalid data is handled safely without fabrication."""

    def test_missing_timestamp_skips_affected_comparison(self):
        transactions = [
            tx("TX300", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            {"transaction_id": "TX301", "beneficiary_id": "BEN900",
             "latitude": 28.6139, "longitude": 77.2090,
             "ration_type": "rice", "quantity": 10},
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_invalid_timestamp_skips_affected_comparison(self):
        transactions = [
            tx("TX302", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX303", "BEN900", "not-a-timestamp", 28.6139, 77.2090),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_missing_coordinates_skips_affected_comparison(self):
        transactions = [
            tx("TX304", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            {"transaction_id": "TX305", "beneficiary_id": "BEN900",
             "timestamp": "2026-08-01T10:05:00",
             "ration_type": "rice", "quantity": 10},
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_invalid_coordinates_skip_affected_comparison(self):
        transactions = [
            tx("TX306", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX307", "BEN900", "2026-08-01T10:05:00", 95.0, 72.8777),  # out of range
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_missing_beneficiary_id_skips_record(self):
        transactions = [
            tx("TX308", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            {"transaction_id": "TX309", "timestamp": "2026-08-01T10:05:00",
             "latitude": 28.6139, "longitude": 77.2090,
             "ration_type": "rice", "quantity": 10},
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_valid_pair_still_detected_alongside_skipped_record(self):
        transactions = [
            tx("TX310", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX311", "BEN900", "2026-08-01T10:05:00", 28.6139, 77.2090),
            {"transaction_id": "TX312", "beneficiary_id": "BEN900",
             "latitude": 12.9716, "longitude": 77.5946,
             "ration_type": "rice", "quantity": 10},
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["anomalies"][0]["transaction_ids"], ["TX310", "TX311"])


class TestAgent1InvalidInput(unittest.TestCase):
    """TEST 6 — invalid input produces clear validation/error handling."""

    def test_non_list_input_raises(self):
        agent = Agent1TransactionAnalyst()
        for bad in ("not a list", None, {"transactions": []}, 42):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    agent.run(bad)

    def test_empty_dataset_returns_empty_anomalies(self):
        result = Agent1TransactionAnalyst().run([])
        self.assertEqual(result, {"anomalies": []})

    def test_malformed_record_is_skipped_not_crashed(self):
        transactions = [
            "not-a-dict",
            tx("TX400", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
            tx("TX401", "BEN900", "2026-08-01T10:05:00", 28.6139, 77.2090),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["anomalies"][0]["transaction_ids"], ["TX400", "TX401"])


class TestAgent1ThresholdBoundary(unittest.TestCase):
    """TEST 7 — behavior around the configured thresholds is deterministic."""

    def test_interval_at_threshold_inclusive(self):
        # Exactly 60 minutes apart and ~100.08 km apart: both inclusive bounds hold.
        transactions = [
            tx("TX500", "BEN900", "2026-08-01T10:00:00", 0.0, 0.0),
            tx("TX501", "BEN900", "2026-08-01T11:00:00", 0.9, 0.0),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(len(result["anomalies"]), 1)

    def test_distance_just_below_threshold_not_flagged(self):
        # ~99.96 km apart: just under the 100 km inclusive bound.
        transactions = [
            tx("TX502", "BEN900", "2026-08-01T10:00:00", 0.0, 0.0),
            tx("TX503", "BEN900", "2026-08-01T11:00:00", 0.899, 0.0),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_interval_just_above_threshold_not_flagged(self):
        # 60.02 minutes apart: just over the 60 min inclusive bound.
        transactions = [
            tx("TX504", "BEN900", "2026-08-01T10:00:00", 0.0, 0.0),
            tx("TX505", "BEN900", "2026-08-01T11:00:01", 2.0, 0.0),
        ]
        result = Agent1TransactionAnalyst().run(transactions)
        self.assertEqual(result, {"anomalies": []})

    def test_thresholds_are_configurable(self):
        transactions = [
            tx("TX506", "BEN900", "2026-08-01T10:00:00", 0.0, 0.0),
            tx("TX507", "BEN900", "2026-08-01T10:45:00", 2.0, 0.0),  # 45 min, ~222 km
        ]
        default = Agent1TransactionAnalyst().run(transactions)
        strict = Agent1TransactionAnalyst(max_interval_minutes=30).run(transactions)
        self.assertEqual(len(default["anomalies"]), 1)
        self.assertEqual(strict, {"anomalies": []})


if __name__ == "__main__":
    unittest.main()
