"""RationRight — multi-agent workflow orchestrator (Phase 6).

Chains the four independently tested agents into one end-to-end workflow:

    Synthetic Dataset
        -> Agent 1 (Transaction Analyst)    -> anomaly candidates
        -> Agent 2 (Anomaly Investigator)   -> verified findings
        -> Agent 3 (Evidence Case Builder)  -> investigation case
        -> Agent 4 (Alert Generator)        -> human-review alert

The orchestrator is normal application logic, NOT another AI agent: it
controls execution order, passes structured outputs between agents, records
stage-attributed failures, and never fabricates results. Every anomaly
candidate from Agent 1 is investigated independently by Agent 2; only verified
findings feed Agent 3. Per-candidate and per-stage failures are recorded in
``errors`` (with stage/anomaly attribution) and do not abort the whole
workflow unnecessarily.

Returned result (workflow-level, not an agent contract):

    {
      "workflow_status": "completed" | "partial_failure" | "failed",
      "stages": {"agent_1": ..., "agent_2": ..., "agent_3": ..., "agent_4": ...},
      "anomalies": [...],            # all Agent 1 candidates
      "unverified_findings": [...],  # Agent 2 findings that were NOT verified
      "findings": [...],             # verified findings (fed to Agent 3)
      "cases": [...],                # investigation cases
      "alerts": [...],               # human-review alerts
      "errors": [...]                # stage-attributed failures
    }

IDs are preserved end to end (anomaly_id -> finding.anomaly_id ->
case.finding_ids -> alert.case_id), so every alert stays traceable back to the
source transactions. Zero anomalies is a normal, successful outcome.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst
from agents.agent_2_anomaly_investigator import (
    DEFAULT_MAX_INTERVAL_MINUTES,
    DEFAULT_MIN_DISTANCE_KM,
    Agent2AnomalyInvestigator,
)
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
from agents.agent_4_alert_generator import Agent4AlertGenerator

logger = logging.getLogger("rationright.workflow")


def run_workflow(
    transactions,
    *,
    max_interval_minutes=DEFAULT_MAX_INTERVAL_MINUTES,
    min_distance_km=DEFAULT_MIN_DISTANCE_KM,
    agent_1=None,
    agent_2=None,
    agent_3=None,
    agent_4=None,
) -> dict:
    """Run the complete RationRight workflow and return the final result.

    ``agent_1``..``agent_4`` are optional injected agent instances (each must
    expose the same ``run`` interface); by default the real agents are used.
    """
    result = {
        "workflow_status": "completed",
        "stages": {
            "agent_1": "pending",
            "agent_2": "pending",
            "agent_3": "pending",
            "agent_4": "pending",
        },
        "timings": {},
        "anomalies": [],
        "unverified_findings": [],
        "findings": [],
        "cases": [],
        "alerts": [],
        "errors": [],
    }

    _started = time.perf_counter()
    _wall_start = time.time()

    def _elapsed() -> float:
        return time.perf_counter() - _started

    def _record_timing(stage: str) -> None:
        """Record a real wall-clock start/end/duration for one agent stage.

        The command center shows these timestamps verbatim — nothing is
        invented. ``started_at`` is the first time this stage's clock is
        observed, ``ended_at`` the last; ``duration_ms`` is measured.
        """
        entry = result["timings"].get(stage) or {}
        entry["started_at"] = entry.get("started_at") or datetime.fromtimestamp(
            _wall_start, tz=timezone.utc
        ).isoformat(timespec="seconds")
        entry["ended_at"] = datetime.fromtimestamp(
            time.time(), tz=timezone.utc
        ).isoformat(timespec="seconds")
        entry["duration_ms"] = int((time.time() - _wall_start) * 1000)
        result["timings"][stage] = entry

    logger.info("[RationRight] Workflow started")

    # ---- Stage 1: Agent 1 — detection -------------------------------------
    logger.info("[Agent 1] Loading transactions")
    stage_agent_1 = agent_1 if agent_1 is not None else Agent1TransactionAnalyst(
        max_interval_minutes=max_interval_minutes,
        min_distance_km=min_distance_km,
    )
    try:
        agent_1_output = stage_agent_1.run(transactions)
    except Exception as exc:  # noqa: BLE001
        result["workflow_status"] = "failed"
        result["stages"]["agent_1"] = "failed"
        result["errors"].append({"stage": "agent_1", "status": "failed", "error": str(exc)})
        logger.error("[Agent 1] Failed: %s", exc)
        logger.info("[RationRight] Workflow failed at agent_1")
        return result

    if not isinstance(agent_1_output, dict) or not isinstance(agent_1_output.get("anomalies"), list):
        result["workflow_status"] = "failed"
        result["stages"]["agent_1"] = "failed"
        result["errors"].append({
            "stage": "agent_1",
            "status": "failed",
            "error": "Agent 1 returned an invalid result (expected {'anomalies': [...]})",
        })
        logger.error("[Agent 1] Returned an invalid result")
        return result

    anomalies = agent_1_output["anomalies"]
    result["stages"]["agent_1"] = "completed"
    result["anomalies"] = anomalies
    _record_timing("agent_1")
    logger.info(
        "[Agent 1] %d transaction(s) analyzed; %d anomaly candidate(s) detected "
        "(%.3fs)",
        len(transactions),
        len(anomalies),
        _elapsed(),
    )

    if not anomalies:
        result["stages"]["agent_2"] = "skipped"
        result["stages"]["agent_3"] = "skipped"
        result["stages"]["agent_4"] = "skipped"
        _record_timing("agent_2")
        _record_timing("agent_3")
        _record_timing("agent_4")
        logger.info(
            "[RationRight] No anomalies detected; workflow completed with no "
            "findings, cases, or alerts"
        )
        return result

    # ---- Stage 2: Agent 2 — verification (one run per candidate) ----------
    stage_agent_2 = agent_2 if agent_2 is not None else Agent2AnomalyInvestigator(
        max_interval_minutes=max_interval_minutes,
        min_distance_km=min_distance_km,
    )
    verified_findings = []
    unverified_findings = []
    for index, anomaly in enumerate(anomalies, start=1):
        anomaly_id = anomaly.get("anomaly_id", "<unknown>")
        logger.info("[Agent 2] Investigating %s", anomaly_id)
        try:
            finding = stage_agent_2.run(
                {"anomaly": anomaly, "transactions": transactions},
                finding_id=f"FIND{index:03d}",
            )
        except Exception as exc:  # noqa: BLE001
            result["errors"].append({
                "stage": "agent_2",
                "anomaly_id": anomaly_id,
                "status": "failed",
                "error": str(exc),
            })
            logger.error("[Agent 2] Failed for %s: %s", anomaly_id, exc)
            continue
        if isinstance(finding, dict) and finding.get("status") == "verified":
            verified_findings.append(finding)
            logger.info("[Agent 2] Finding %s verified", finding.get("finding_id", "<unknown>"))
        else:
            unverified_findings.append(finding)
            logger.info(
                "[Agent 2] Finding %s unverified for %s",
                finding.get("finding_id", "<unknown>") if isinstance(finding, dict) else "<invalid>",
                anomaly_id,
            )
    result["stages"]["agent_2"] = "completed"
    result["findings"] = verified_findings
    result["unverified_findings"] = unverified_findings
    _record_timing("agent_2")
    logger.info("[Agent 2] %d verified, %d unverified (%.3fs)",
                len(verified_findings), len(unverified_findings), _elapsed())

    if not verified_findings:
        result["stages"]["agent_3"] = "skipped"
        result["stages"]["agent_4"] = "skipped"
        _record_timing("agent_3")
        _record_timing("agent_4")
        logger.info(
            "[RationRight] No verified findings; workflow completed without a case or alert"
        )
        return _finalize(result)

    # ---- Stage 3: Agent 3 — case building ---------------------------------
    stage_agent_3 = agent_3 if agent_3 is not None else Agent3EvidenceCaseBuilder()
    logger.info("[Agent 3] Building case from %d finding(s)", len(verified_findings))
    try:
        case = stage_agent_3.run({"findings": verified_findings, "transactions": transactions})
    except Exception as exc:  # noqa: BLE001
        result["stages"]["agent_3"] = "failed"
        result["errors"].append({"stage": "agent_3", "status": "failed", "error": str(exc)})
        logger.error("[Agent 3] Failed: %s", exc)
        return _finalize(result)
    result["cases"].append(case)
    result["stages"]["agent_3"] = "completed"
    _record_timing("agent_3")
    logger.info("[Agent 3] Case %s %s (%.3fs)", case.get("case_id"), case.get("status"), _elapsed())

    if case.get("status") != "requires_human_review":
        result["stages"]["agent_4"] = "skipped"
        _record_timing("agent_4")
        logger.info("[Agent 4] Skipped: case %s is not ready for review", case.get("case_id"))
        return _finalize(result)

    # ---- Stage 4: Agent 4 — alert generation ------------------------------
    stage_agent_4 = agent_4 if agent_4 is not None else Agent4AlertGenerator()
    logger.info("[Agent 4] Generating alert for %s", case["case_id"])
    try:
        alert = stage_agent_4.run(case)
    except Exception as exc:  # noqa: BLE001
        result["stages"]["agent_4"] = "failed"
        result["errors"].append({
            "stage": "agent_4",
            "case_id": case.get("case_id"),
            "status": "failed",
            "error": str(exc),
        })
        logger.error("[Agent 4] Failed: %s", exc)
        return _finalize(result)
    result["alerts"].append(alert)
    result["stages"]["agent_4"] = "completed"
    _record_timing("agent_4")
    logger.info("[Agent 4] Alert %s ready for human review (%.3fs)", alert["alert_id"], _elapsed())

    return _finalize(result)


def _finalize(result: dict) -> dict:
    """Set the final workflow status and log completion."""
    result["workflow_status"] = "partial_failure" if result["errors"] else "completed"
    logger.info(
        "[RationRight] Workflow %s (stages: %s)",
        result["workflow_status"],
        result["stages"],
    )
    return result
