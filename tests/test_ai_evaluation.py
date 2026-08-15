"""RationRight — Phase 15: AI evaluation & accuracy.

Evaluates the LLM narrative layer WITHOUT calling any model: injected
generators record exactly what the agents send and return scripted text, so
every assertion is deterministic. The scorecard at the bottom of this module
is the Phase 15 AI evaluation table; the tests below are its evidence.

What is verified:

- Number accuracy: the context handed to the LLM contains the exact
  calculated values, and the structured result is never altered by the LLM.
- Hallucination refusal: an LLM that invents numbers cannot contaminate the
  structured output; the deterministic path never invents missing values.
- Source accuracy: imported data is attributed to the real source, never
  claimed as a live government API.
- Recommendation evidence: recommendations are produced only from supplied
  evidence, and are labelled as AI recommendation / decision support.
- Confidence provenance: confidence is a deterministic code constant, not an
  LLM number.
- Failure modes: timeout / 429 / 500 / malformed response / missing key all
  degrade to the deterministic fallback without raising.
- No infinite retry: a failing generator is called exactly once.
- Context hygiene: no secrets or unrelated rows are sent to the model.

Run from the project root::

    python3 -m unittest tests.test_ai_evaluation -v
"""

import os
import tempfile
import unittest
import urllib.error
from pathlib import Path

import database as db
import simulation as sim
from agents import llm
from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
from agents.agent_4_alert_generator import Agent4AlertGenerator
from ingestion import service as ingest
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

TRANSACTION_CSV = (
    "Transaction ID,Beneficiary ID,FPS Code,Transaction Date,Commodity,Quantity,Unit\n"
    "TX201,BEN001,FPS01,2026-08-01,rice,100,kg\n"
    "TX202,BEN001,FPS01,2026-08-02,rice,40,kg\n"
    "TX203,BEN002,FPS02,2026-08-03,wheat,20,kg\n"
    "TX204,BEN002,FPS02,2026-08-04,pulses,60,kg\n"
)


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    os.unlink(tmp.name)
    return tmp.name


def _seed_import_with_inventory(db_path):
    """Import the CSV above and add rice inventory; returns the import id."""
    upload = ingest.handle_upload(TRANSACTION_CSV.encode(), "eval.csv", "text/csv")
    ingest.validate_step(upload["token"], dataset_type="ration_transactions",
                         db_path=db_path)
    summary = ingest.confirm_step(upload["token"], db_path=db_path)
    imp_id = summary["data_import_id"]
    conn = db.open_db(db_path)
    try:
        center = conn.execute(
            "SELECT id FROM fps_centers WHERE fps_code = 'FPS01'").fetchone()
        db.insert_inventory_batch(conn, [
            {"fps_center_id": center["id"], "commodity": "rice",
             "current_stock": 3400.0, "monthly_consumption": 1200.0,
             "reorder_threshold": 1500.0, "source_import_id": imp_id},
        ])
        conn.commit()
    finally:
        conn.close()
    return imp_id


class RecordingGenerator:
    """Records every call; returns a scripted string or raises."""

    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def __call__(self, kind, context, fallback):
        self.calls.append((kind, dict(context), fallback))
        if self.exc is not None:
            raise self.exc
        if self.result is not None:
            return self.result
        return "Generated narrative for %s." % kind


class NumberAccuracyTests(unittest.TestCase):
    """The LLM receives exact calculated values; structured output is code-owned."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.imp_id = _seed_import_with_inventory(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_scenario_context_matches_calculated_result(self):
        gen = RecordingGenerator(result="AI scenario interpretation.")
        result = sim.run_scenario(self.imp_id, commodity="rice",
                                  demand_change_pct=10, db_path=self.db_path,
                                  generator=gen)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(gen.calls), 1)
        kind, context, fallback = gen.calls[0]
        self.assertEqual(kind, "scenario_interpretation")

        # Every number the AI receives is exactly the code-computed value.
        self.assertEqual(context["baseline_monthly_demand_kg"],
                         result["baseline"]["monthly_demand_kg"])
        self.assertEqual(context["scenario_monthly_demand_kg"],
                         result["scenario"]["projected_monthly_demand_kg"])
        self.assertEqual(context["current_stock_kg"], 3400.0)
        self.assertEqual(context["coverage_days_projected"],
                         result["scenario"]["projected_coverage_days"])
        self.assertEqual(context["reorder_threshold"], 1500.0)
        self.assertEqual(context["risk"], result["risk"])

        # The deterministic explanation also carries the same numbers.
        self.assertIn("1500.0", fallback)  # reorder threshold

    def test_scenario_math_is_deterministic_not_llm(self):
        gen = RecordingGenerator(result="the projected demand is 999999 kg")
        result = sim.run_scenario(self.imp_id, commodity="rice",
                                  demand_change_pct=10, db_path=self.db_path,
                                  generator=gen)
        # 140 kg over 1 month -> 140; +10% -> 154. The LLM's invented 999999
        # must not appear anywhere in the structured result.
        self.assertEqual(result["scenario"]["projected_monthly_demand_kg"], 154.0)
        self.assertNotEqual(result["scenario"]["projected_monthly_demand_kg"], 999999)
        # Projected daily consumption is the baseline times the multiplier.
        baseline_daily = result["baseline"]["daily_consumption_kg"]
        self.assertEqual(result["scenario"]["projected_daily_consumption_kg"],
                         round(baseline_daily * 1.1, 2))


class HallucinationRefusalTests(unittest.TestCase):
    """An LLM that invents facts cannot contaminate structured output."""

    def test_hostile_generator_cannot_change_evidence_or_severity(self):
        gen = RecordingGenerator(
            result="INVENTED: stock is 42 kg, fraud confirmed, district Chennai.")
        finding = Agent2AnomalyInvestigator(narrative_generator=gen).run(
            A2_PAYLOAD, finding_id="FIND001")
        # Structured fields are calculated, never overwritten by the narrative.
        self.assertEqual(finding["evidence"]["time_difference_minutes"], 12.0)
        self.assertEqual(finding["evidence"]["distance_km"], 1148.09)
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["transaction_ids"], ["TX001", "TX002"])
        # Guilt language is rejected at the sanitizer, falling back to the
        # deterministic text that uses only supplied values.
        self.assertNotIn("fraud", finding["explanation"].lower())
        self.assertIn("12.00 minutes", finding["explanation"])

    def test_deterministic_path_never_invents_missing_values(self):
        # No generator, LLM disabled: fallback explanation must only reference
        # values that exist in the payload.
        finding = Agent2AnomalyInvestigator().run(A2_PAYLOAD, finding_id="FIND001")
        explanation = finding["explanation"].lower()
        for invented in ("42 kg", "chennai", "mumbai", "delhi"):
            self.assertNotIn(invented, explanation)
        # It must reference the real evidence.
        self.assertIn("1148.09", finding["explanation"])
        self.assertIn("12.00", finding["explanation"])

    def test_insufficient_data_is_refused_not_estimated(self):
        # A scenario with no matching transactions returns INSUFFICIENT_DATA,
        # not a fabricated forecast.
        db_path = _fresh_db()
        try:
            conn = db.open_db(db_path)
            conn.close()
            r = sim.run_scenario(999999, commodity="rice", db_path=db_path)
            self.assertEqual(r["status"], "INSUFFICIENT_DATA")
            self.assertIsNone(r.get("risk"))
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class SourceAccuracyTests(unittest.TestCase):
    """Imported data is attributed honestly; no fake live-source claims."""

    def setUp(self):
        self.db_path = _fresh_db()
        self.imp_id = _seed_import_with_inventory(self.db_path)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.unlink(self.db_path))

    def test_imported_source_is_labeled_uploaded_dataset(self):
        conn = db.open_db(self.db_path)
        try:
            sources = conn.execute(
                "SELECT name, type, status FROM data_sources").fetchall()
            import_row = conn.execute(
                "SELECT dataset_name, file_name FROM data_imports "
                "WHERE id = ?", (self.imp_id,)).fetchone()
        finally:
            conn.close()
        names = [s["name"] for s in sources]
        self.assertIn("Uploaded Dataset", names)
        self.assertTrue(import_row["dataset_name"])

    def test_command_center_disclaimer_is_honest(self):
        import command_center
        cc = command_center.command_center(db_path=self.db_path)
        disclaimer = cc["disclaimer"].lower()
        self.assertIn("imported", disclaimer)
        self.assertNotIn("live government", disclaimer)
        self.assertNotIn("government api", disclaimer)
        # Source list must not invent a government source.
        source_names = [s["name"].lower() for s in cc["sources"]]
        self.assertTrue(any("uploaded" in n for n in source_names))

    def test_report_source_label_matches_import(self):
        import command_center
        report = command_center.generate_report(db_path=self.db_path)
        self.assertIn("Uploaded Dataset", report["source"])
        self.assertNotIn("government", report["source"].lower())


class RecommendationEvidenceTests(unittest.TestCase):
    """Recommendations exist only where evidence supports them."""

    def test_agent_4_message_is_decision_support_not_an_accusation(self):
        case = Agent3EvidenceCaseBuilder().run(
            {"findings": [Agent2AnomalyInvestigator().run(
                A2_PAYLOAD, finding_id="FIND001")], "transactions": TX})
        gen = RecordingGenerator(result="Review this potential anomaly.")
        alert = Agent4AlertGenerator(narrative_generator=gen).run(case)
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(alert["message"], "Review this potential anomaly.")
        # The recommendation field is deterministic and decision-support framed.
        recommendation = alert["recommended_action"].lower()
        self.assertIn("human verification", recommendation)

    def test_no_evidence_is_refused_not_fabricated(self):
        # Agent 4's own contract refuses to build an alert from a case with no
        # findings — it will not invent a recommendation from nothing.
        with self.assertRaises(ValueError):
            Agent4AlertGenerator().run({
                "case_id": "CASE000", "status": "requires_human_review",
                "severity": "high", "evidence": [], "confidence": 0.5,
                "summary": "No verified findings.", "finding_ids": [],
            })


class ConfidenceProvenanceTests(unittest.TestCase):
    """Confidence is a deterministic constant, never an LLM number."""

    def test_agent_3_confidence_is_code_constant(self):
        gen = RecordingGenerator(result="confidence: 0.13")
        case = Agent3EvidenceCaseBuilder(narrative_generator=gen).run(
            {"findings": [Agent2AnomalyInvestigator().run(
                A2_PAYLOAD, finding_id="FIND001")], "transactions": TX})
        self.assertEqual(case["confidence"], 0.9)  # VERIFIED_CONFIDENCE
        self.assertNotEqual(case["confidence"], 0.13)

    def test_generator_cannot_inject_confidence(self):
        from agents.agent_3_evidence_case_builder import VERIFIED_CONFIDENCE
        self.assertEqual(VERIFIED_CONFIDENCE, 0.9)
        gen = RecordingGenerator(result="case is 99.9% certain")
        case = Agent3EvidenceCaseBuilder(narrative_generator=gen).run(
            {"findings": [Agent2AnomalyInvestigator().run(
                A2_PAYLOAD, finding_id="FIND001")], "transactions": TX})
        self.assertEqual(case["confidence"], 0.9)


class FailureModeTests(unittest.TestCase):
    """Every AI failure degrades to the deterministic fallback, never raises."""

    def _assert_fallback(self, exc):
        gen = RecordingGenerator(exc=exc)
        finding = Agent2AnomalyInvestigator(narrative_generator=gen).run(
            A2_PAYLOAD, finding_id="FIND001")
        self.assertEqual(finding["status"], "verified")
        self.assertEqual(finding["evidence"]["distance_km"], 1148.09)
        self.assertIn("1148.09", finding["explanation"])
        self.assertEqual(len(gen.calls), 1)

    def test_timeout(self):
        self._assert_fallback(TimeoutError("connection timed out"))

    def test_http_429(self):
        self._assert_fallback(urllib.error.HTTPError(
            "url", 429, "Too Many Requests", None, None))

    def test_http_500(self):
        self._assert_fallback(urllib.error.HTTPError(
            "url", 500, "Internal Server Error", None, None))

    def test_malformed_response(self):
        self._assert_fallback(ValueError("completion response contained no choices"))

    def test_network_failure(self):
        self._assert_fallback(urllib.error.URLError("connection refused"))

    def test_missing_key_uses_fallback_without_call(self):
        for name in ("RATIONRIGHT_LLM_ENABLED", "OPENAI_API_KEY"):
            os.environ.pop(name, None)
        try:
            result = llm.maybe_generate("agent_2_explanation",
                                        {"x": 1}, "deterministic text")
            self.assertEqual(result, "deterministic text")
        finally:
            os.environ.pop("RATIONRIGHT_LLM_ENABLED", None)
            os.environ.pop("OPENAI_API_KEY", None)


class RetryBehaviorTests(unittest.TestCase):
    """Failures fail fast: exactly one attempt, no infinite retry loop."""

    def test_failing_generator_called_exactly_once(self):
        gen = RecordingGenerator(exc=RuntimeError("provider down"))
        result = llm.maybe_generate("agent_2_explanation", {"x": 1},
                                    "fallback text", generator=gen)
        self.assertEqual(result, "fallback text")
        self.assertEqual(len(gen.calls), 1)

    def test_persistent_failure_resolves_immediately(self):
        import time
        gen = RecordingGenerator(exc=RuntimeError("down"))
        started = time.monotonic()
        for _ in range(3):
            llm.maybe_generate("scenario_interpretation", {"x": 1},
                               "fallback", generator=gen)
        elapsed = time.monotonic() - started
        self.assertEqual(len(gen.calls), 3)
        self.assertLess(elapsed, 2.0, "must not sleep/backoff between failures")


class ContextHygieneTests(unittest.TestCase):
    """Only relevant facts reach the model; never secrets or raw rows."""

    def test_context_contains_no_secrets_or_unrelated_data(self):
        gen = RecordingGenerator()
        Agent2AnomalyInvestigator(narrative_generator=gen).run(
            A2_PAYLOAD, finding_id="FIND001")
        _, context, _ = gen.calls[0]
        blob = str(context).lower()
        for secret in ("api_key", "openai", "token", "password", "secret",
                       "authorization", "bearer"):
            self.assertNotIn(secret, blob)
        # Only the two transactions under investigation are referenced.
        self.assertNotIn("TX099", blob)

    def test_executive_summary_context_is_aggregated_not_raw(self):
        import command_center
        gen = RecordingGenerator()
        db_path = _fresh_db()
        try:
            ingest.handle_upload(TRANSACTION_CSV.encode(), "e.csv", "text/csv")
            up = ingest.handle_upload(TRANSACTION_CSV.encode(), "e.csv", "text/csv")
            ingest.validate_step(up["token"], dataset_type="ration_transactions",
                                 db_path=db_path)
            ingest.confirm_step(up["token"], db_path=db_path)
            cc = command_center.command_center(db_path=db_path, generator=gen)
            self.assertIn("generated_by", cc["executive_summary"])
            # The summary context is aggregated: KPIs + counts, not row data.
            if cc["executive_summary"].get("context"):
                ctx = cc["executive_summary"]["context"]
                self.assertNotIn("ration_transactions", str(ctx))
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class EvaluationScorecardTests(unittest.TestCase):
    """The Phase 15 AI evaluation table — every row must PASS."""

    def test_scorecard(self):
        scorecard = []
        # Row 1: missing data -> refuse (insufficient), never estimate.
        db_path = _fresh_db()
        try:
            conn = db.open_db(db_path)
            conn.close()
            r = sim.run_scenario(999999, commodity="rice", db_path=db_path)
            refused = r["status"] == "INSUFFICIENT_DATA" and r.get("risk") is None
            scorecard.append(("Missing data -> refuse", "INSUFFICIENT_DATA",
                              r["status"], "PASS" if refused else "FAIL"))
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

        # Row 2: number preservation in scenario context.
        db_path = _fresh_db()
        try:
            imp = _seed_import_with_inventory(db_path)
            gen = RecordingGenerator()
            sim.run_scenario(imp, commodity="rice", demand_change_pct=10,
                             db_path=db_path, generator=gen)
            ctx = gen.calls[0][1]
            scorecard.append(
                ("Number accuracy (context == calculated)",
                 "exact values", "matches", "PASS"
                 if ctx["scenario_monthly_demand_kg"] == 154.0 else "FAIL"))
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

        # Row 3: source attribution is honest.
        db_path = _fresh_db()
        try:
            _seed_import_with_inventory(db_path)
            import command_center
            cc = command_center.command_center(db_path=db_path)
            honest = ("imported dataset" in cc["disclaimer"].lower()
                      and "live government" not in cc["disclaimer"].lower()
                      and "uploaded dataset" in [s["name"].lower()
                                                 for s in cc["sources"]])
            scorecard.append(("Source attribution (imported, not live API)",
                              "honest", "honest" if honest else "misleading",
                              "PASS" if honest else "FAIL"))
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

        # Row 4: confidence is deterministic.
        gen = RecordingGenerator(result="confidence: 0.01")
        case = Agent3EvidenceCaseBuilder(narrative_generator=gen).run(
            {"findings": [Agent2AnomalyInvestigator().run(
                A2_PAYLOAD, finding_id="FIND001")], "transactions": TX})
        deterministic = case["confidence"] == 0.9
        scorecard.append(("Confidence provenance (deterministic)",
                          "0.9", case["confidence"], "PASS" if deterministic else "FAIL"))

        # Row 5: AI failure degrades gracefully.
        gen = RecordingGenerator(exc=urllib.error.URLError("down"))
        finding = Agent2AnomalyInvestigator(narrative_generator=gen).run(
            A2_PAYLOAD, finding_id="FIND001")
        graceful = finding["status"] == "verified" and len(gen.calls) == 1
        scorecard.append(("AI failure -> fallback, no retry storm",
                          "graceful", "graceful" if graceful else "crashed",
                          "PASS" if graceful else "FAIL"))

        rows = "\n".join("| %s | %s | %s | %s |" % row for row in scorecard)
        print("\nAI EVALUATION SCORECARD\n" + rows)
        for row in scorecard:
            self.assertEqual(row[3], "PASS", row[0])


if __name__ == "__main__":
    unittest.main()
