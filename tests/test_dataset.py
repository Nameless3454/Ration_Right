"""RationRight — Phase 1: synthetic dataset tests.

Run from the project root::

    python -m unittest discover -s tests -t . -v
"""

import unittest
from datetime import datetime

from scripts.validate_dataset import (
    DEFAULT_DATASET_PATH,
    LARGE_DISTANCE_KM,
    PLANTED_ANOMALY_IDS,
    SHORT_INTERVAL_MINUTES,
    find_suspicious_pairs,
    load_dataset,
    validate_transactions,
    verify_planted_anomaly,
)


class TestSyntheticDataset(unittest.TestCase):
    """All tests against the checked-in synthetic dataset."""

    @classmethod
    def setUpClass(cls):
        cls.dataset = load_dataset(DEFAULT_DATASET_PATH)
        cls.transactions = cls.dataset["transactions"]

    def test_01_dataset_loads_successfully(self):
        """TEST 1: dataset loads and is clearly labeled synthetic."""
        self.assertIsInstance(self.dataset, dict)
        self.assertIsInstance(self.transactions, list)
        self.assertGreater(len(self.transactions), 0)
        metadata = self.dataset.get("metadata", {})
        self.assertIn("Synthetic Demo Data", metadata.get("label", ""))

    def test_02_transaction_ids_are_unique(self):
        """TEST 2: every transaction_id appears exactly once."""
        ids = [tx["transaction_id"] for tx in self.transactions]
        self.assertEqual(len(ids), len(set(ids)))

    def test_03_all_required_fields_exist(self):
        """TEST 3: every record has all seven documented contract fields."""
        required = {
            "transaction_id",
            "beneficiary_id",
            "timestamp",
            "latitude",
            "longitude",
            "ration_type",
            "quantity",
        }
        for tx in self.transactions:
            with self.subTest(transaction_id=tx.get("transaction_id")):
                self.assertTrue(required.issubset(tx.keys()), tx)

    def test_04_timestamps_are_valid(self):
        """TEST 4: every timestamp parses as ISO-8601."""
        for tx in self.transactions:
            with self.subTest(transaction_id=tx["transaction_id"]):
                datetime.fromisoformat(tx["timestamp"])

    def test_05_coordinates_are_valid(self):
        """TEST 5: latitudes in [-90, 90] and longitudes in [-180, 180]."""
        for tx in self.transactions:
            with self.subTest(transaction_id=tx["transaction_id"]):
                self.assertTrue(-90 <= tx["latitude"] <= 90, tx)
                self.assertTrue(-180 <= tx["longitude"] <= 180, tx)

    def test_06_quantities_are_valid(self):
        """TEST 6: every quantity is positive."""
        for tx in self.transactions:
            with self.subTest(transaction_id=tx["transaction_id"]):
                self.assertGreater(tx["quantity"], 0)

    def test_07_planted_anomaly_transactions_exist(self):
        """TEST 7: the planted anomaly transaction IDs are present."""
        ids = {tx["transaction_id"] for tx in self.transactions}
        for tx_id in PLANTED_ANOMALY_IDS:
            with self.subTest(transaction_id=tx_id):
                self.assertIn(tx_id, ids)

    def test_08_planted_anomaly_satisfies_pattern(self):
        """TEST 8: the planted pair shares a beneficiary, is within the short
        interval, and is geographically far apart."""
        report = verify_planted_anomaly(self.transactions)
        self.assertTrue(report["present"], report)
        self.assertTrue(report["pattern_satisfied"], report)
        self.assertTrue(report["conditions"]["same_beneficiary"], report)
        self.assertTrue(report["conditions"]["short_time_interval"], report)
        self.assertTrue(report["conditions"]["large_geographic_distance"], report)
        self.assertLessEqual(report["time_difference_minutes"], SHORT_INTERVAL_MINUTES)
        self.assertGreaterEqual(report["distance_km"], LARGE_DISTANCE_KM)

    def test_09_normal_transactions_do_not_trip_threshold(self):
        """TEST 9: the planted pair is the ONLY pair meeting the thresholds —
        normal and control records must not accidentally match."""
        pairs = find_suspicious_pairs(self.transactions)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["transaction_ids"], sorted(PLANTED_ANOMALY_IDS))

    def test_10_full_schema_validation_has_no_errors(self):
        """Full contract validation passes with zero errors."""
        self.assertEqual(validate_transactions(self.transactions), [])


if __name__ == "__main__":
    unittest.main()
