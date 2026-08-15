"""RationRight — Phase 6: multi-agent workflow integration tests.

Run from the project root::

    python3 -m unittest discover -s tests -t . -v
"""

import unittest

from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from scripts.validate_dataset import DEFAULT_DATASET_PATH, haversine_km, load_dataset
from workflow import run_workflow

REAL_TRANSACTIONS = load_dataset(DEFAULT_DATASET_PATH)["transactions"]


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


def multi_anomaly_transactions():
    """Two independent planted rapid-geographic pairs (different beneficiaries)."""
    return [
        make_tx("TX100", "BEN900", "2026-08-01T10:00:00", 19.0760, 72.8777),
        make_tx("TX101", "BEN900", "2026-08-01T10:05:00", 28.6139, 77.2090),
        make_tx("TX102", "BEN901", "2026-08-01T11:00:00", 18.5204, 73.8567),
        make_tx("TX103", "BEN901", "2026-08-01T11:10:00", 12.9716, 77.5946),
    ]


def failing_agent_2(fail_for):
    """Wrap the real Agent 2 but raise for the given anomaly IDs."""
    real = Agent2AnomalyInvestigator()

    class _Wrapper:
        def run(self, payload, finding_id="FIND001"):
            anomaly_id = payload["anomaly"]["anomaly_id"]
            if anomaly_id in fail_for:
                raise ValueError(f"forced Agent 2 failure for {anomaly_id}")
            return real.run(payload, finding_id=finding_id)

    return _Wrapper()


def failing_agent_3():
    class _Wrapper:
        def run(self, payload):
            raise ValueError("forced Agent 3 failure")

    return _Wrapper()


def failing_agent_4():
    class _Wrapper:
        def run(self, case):
            raise ValueError("forced Agent 4 failure")

    return _Wrapper()


def unverified_agent_2():
    """Agent 2 stand-in that returns an unverified finding for every candidate."""

    class _Wrapper:
        def run(self, payload, finding_id="FIND001"):
            anomaly = payload["anomaly"]
            return {
                "finding_id": finding_id,
                "anomaly_id": anomaly["anomaly_id"],
                "status": "unverified",
                "transaction_ids": list(anomaly["transaction_ids"]),
                "evidence": {},
                "evidence_sources": [],
                "explanation": "Test candidate could not be verified.",
            }

    return _Wrapper()


class TestWorkflowHappyPath(unittest.TestCase):
    """TEST 1 — the real planted anomaly completes the full chain."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_workflow(REAL_TRANSACTIONS)

    def test_workflow_completed(self):
        self.assertEqual(self.result["workflow_status"], "completed")
        self.assertEqual(
            self.result["stages"],
            {
                "agent_1": "completed",
                "agent_2": "completed",
                "agent_3": "completed",
                "agent_4": "completed",
            },
        )
        self.assertEqual(self.result["errors"], [])

    def test_planted_anomaly_reaches_alert(self):
        self.assertEqual(len(self.result["anomalies"]), 1)
        self.assertEqual(len(self.result["findings"]), 1)
        self.assertEqual(len(self.result["cases"]), 1)
        self.assertEqual(len(self.result["alerts"]), 1)
        self.assertEqual(self.result["findings"][0]["status"], "verified")
        self.assertEqual(self.result["alerts"][0]["status"], "open")
        self.assertEqual(self.result["unverified_findings"], [])


class TestWorkflowZeroAnomalies(unittest.TestCase):
    """TEST 2 — a normal dataset completes cleanly with zero alerts."""

    def test_normal_dataset_completes_cleanly(self):
        transactions = [
            t for t in REAL_TRANSACTIONS if t["transaction_id"] not in ("TX001", "TX002")
        ]
        result = run_workflow(transactions)
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(result["anomalies"], [])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["stages"]["agent_1"], "completed")
        self.assertEqual(result["stages"]["agent_2"], "skipped")
        self.assertEqual(result["stages"]["agent_3"], "skipped")
        self.assertEqual(result["stages"]["agent_4"], "skipped")


class TestWorkflowMultipleAnomalies(unittest.TestCase):
    """TEST 3 — multiple candidates stay independent; no evidence mixing."""

    def test_candidates_stay_independent(self):
        result = run_workflow(multi_anomaly_transactions())
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(len(result["anomalies"]), 2)
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(len(result["alerts"]), 1)

        case = result["cases"][0]
        self.assertEqual(case["finding_ids"], ["FIND001", "FIND002"])
        values = [e["value"] for e in case["evidence"]]
        self.assertEqual(values[0], 5.0)
        self.assertAlmostEqual(values[1], round(haversine_km(19.0760, 72.8777, 28.6139, 77.2090), 2), places=2)
        self.assertEqual(values[2], 10.0)
        self.assertAlmostEqual(values[3], round(haversine_km(18.5204, 73.8567, 12.9716, 77.5946), 2), places=2)


class TestWorkflowAgent2Failure(unittest.TestCase):
    """TEST 4 — a failing candidate is recorded; valid candidates continue."""

    def test_failed_candidate_recorded_and_others_continue(self):
        result = run_workflow(
            multi_anomaly_transactions(),
            agent_2=failing_agent_2({"ANOM001"}),
        )
        self.assertEqual(result["workflow_status"], "partial_failure")
        self.assertEqual(len(result["errors"]), 1)
        error = result["errors"][0]
        self.assertEqual(error["stage"], "agent_2")
        self.assertEqual(error["anomaly_id"], "ANOM001")
        self.assertEqual(error["status"], "failed")
        self.assertIn("forced Agent 2 failure", error["error"])

        # No fabricated finding for the failed candidate; the other continues.
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["anomaly_id"], "ANOM002")
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(len(result["alerts"]), 1)


class TestWorkflowAgent3Failure(unittest.TestCase):
    """TEST 5 — an Agent 3 failure is recorded with stage attribution."""

    def test_agent_3_failure_recorded(self):
        result = run_workflow(REAL_TRANSACTIONS, agent_3=failing_agent_3())
        self.assertEqual(result["workflow_status"], "partial_failure")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["stage"], "agent_3")
        self.assertEqual(result["stages"]["agent_3"], "failed")
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["alerts"], [])
        # Agent 2 still succeeded and produced its finding.
        self.assertEqual(len(result["findings"]), 1)


class TestWorkflowAgent4Failure(unittest.TestCase):
    """TEST 6 — an Agent 4 failure is recorded with stage attribution."""

    def test_agent_4_failure_recorded(self):
        result = run_workflow(REAL_TRANSACTIONS, agent_4=failing_agent_4())
        self.assertEqual(result["workflow_status"], "partial_failure")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["stage"], "agent_4")
        self.assertEqual(result["stages"]["agent_4"], "failed")
        self.assertEqual(len(result["cases"]), 1)
        self.assertEqual(result["alerts"], [])


class TestWorkflowUnverifiedOnly(unittest.TestCase):
    """No verified findings completes cleanly without a case or alert."""

    def test_all_unverified_completes_without_alert(self):
        result = run_workflow(REAL_TRANSACTIONS, agent_2=unverified_agent_2())
        self.assertEqual(result["workflow_status"], "completed")
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(len(result["unverified_findings"]), 1)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["alerts"], [])
        self.assertEqual(result["stages"]["agent_3"], "skipped")
        self.assertEqual(result["stages"]["agent_4"], "skipped")


class TestWorkflowTraceability(unittest.TestCase):
    """TEST 7 — alert -> case -> finding -> anomaly -> transactions stay connected."""

    def test_ids_connected_end_to_end(self):
        result = run_workflow(REAL_TRANSACTIONS)
        alert = result["alerts"][0]
        case = result["cases"][0]
        finding = result["findings"][0]
        anomaly = result["anomalies"][0]
        self.assertEqual(alert["case_id"], case["case_id"])
        self.assertEqual(case["finding_ids"], [finding["finding_id"]])
        self.assertEqual(finding["anomaly_id"], anomaly["anomaly_id"])
        self.assertEqual(anomaly["transaction_ids"], ["TX001", "TX002"])


class TestWorkflowNoFabrication(unittest.TestCase):
    """TEST 8 — every final alert refers to actual Phase 1 transactions."""

    def test_all_anomaly_transactions_are_real(self):
        result = run_workflow(REAL_TRANSACTIONS)
        real_ids = {t["transaction_id"] for t in REAL_TRANSACTIONS}
        for anomaly in result["anomalies"]:
            self.assertTrue(set(anomaly["transaction_ids"]).issubset(real_ids))
        # The alert's evidence values match the real calculation end to end.
        alert_message = result["alerts"][0]["message"]
        self.assertIn("12.0", alert_message)
        self.assertIn("1148.09", alert_message)


class TestWorkflowRepeatability(unittest.TestCase):
    """TEST 9 — repeated runs on the same data are identical."""

    def test_results_are_identical_across_runs(self):
        first = run_workflow(REAL_TRANSACTIONS)
        for _ in range(2):
            again = run_workflow(REAL_TRANSACTIONS)
            self.assertEqual(again["workflow_status"], first["workflow_status"])
            self.assertEqual(again["anomalies"], first["anomalies"])
            self.assertEqual(again["findings"], first["findings"])
            self.assertEqual(again["cases"], first["cases"])
            self.assertEqual(again["alerts"], first["alerts"])


class TestWorkflowInvalidInput(unittest.TestCase):
    """Catastrophic input fails at the attributed stage, not vaguely."""

    def test_invalid_input_reported_at_agent_1(self):
        result = run_workflow("not a list of transactions")
        self.assertEqual(result["workflow_status"], "failed")
        self.assertEqual(result["stages"]["agent_1"], "failed")
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(result["errors"][0]["stage"], "agent_1")
        self.assertIn("list", result["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
