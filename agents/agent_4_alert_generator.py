"""RationRight — Agent 4: Alert Generator (Phase 5).

Final decision-support layer of the MVP: transforms the Agent 3 investigation
case into a concise, dashboard-ready alert for HUMAN REVIEW. The alert follows
the documented Alert schema in ``RationRight_complete_docs/data_contract.md``:

    {"alert_id", "case_id", "severity", "title", "message",
     "recommended_action", "status"}

Deterministic rules used by this agent (documented, no LLM decisions):
- ``severity`` (which the future UI renders as alert priority) is PRESERVED
  from the Agent 3 case — never invented or chosen arbitrarily.
- ``status == "open"`` for a ready review alert (the documented equivalent of
  "pending human review": an open alert awaiting human review). A case that is
  not ready (``status != "requires_human_review"``) or that lacks the required
  verified evidence produces ``status == "not_ready"`` with ``severity``
  ``"low"`` — no normal review alert is generated from incomplete input.
- ``recommended_action`` is taken from the case and always ends as
  "Human verification" — the agent never blocks, denies, suspends, punishes,
  or takes automatic enforcement action.
- The ``message`` is built deterministically from the case's verified evidence
  values, which are preserved exactly (no recalculation, no rounding, no
  "approximately"). No transaction, beneficiary, or identity is ever guessed:
  the documented Alert schema carries no such fields, so none are invented.

The alert describes evidence and recommends review; it does not establish guilt.

Run standalone::

    python3 scripts/run_agent_4.py

Import::

    from agents.agent_4_alert_generator import Agent4AlertGenerator
"""

from __future__ import annotations

import logging

from agents.llm import maybe_generate

logger = logging.getLogger("rationright.agent_4")

ALERT_FIELDS = (
    "alert_id",
    "case_id",
    "severity",
    "title",
    "message",
    "recommended_action",
    "status",
)

READY_STATUS = "open"          # documented equivalent of "pending human review"
NOT_READY_STATUS = "not_ready"
NOT_READY_SEVERITY = "low"     # no verified evidence to escalate
TITLE = "Potential transaction anomaly detected"
NOT_READY_TITLE = "Alert not ready for review"
SUPPORTED_SEVERITIES = ("high", "medium", "low")


class Agent4AlertGenerator:
    """Alert Generator: converts a completed case into a review alert."""

    def __init__(self, narrative_generator=None):
        self.narrative_generator = narrative_generator

    def run(self, payload) -> dict:
        """Generate one alert from an Agent 3 investigation case.

        ``payload`` is the case object produced by Agent 3 (the documented
        Investigation Case schema).
        """
        logger.info("Agent 4 started")
        case = payload
        if not isinstance(case, dict):
            raise ValueError(
                "payload must be the investigation case object produced by Agent 3"
            )
        logger.info("Case received: %s", case.get("case_id", "<missing>"))

        self._validate_case(case)
        logger.info("Case validation: OK (status=%s)", case["status"])

        if case["status"] != "requires_human_review":
            logger.warning(
                "Case is not ready for review (status=%s); generating not-ready alert.",
                case["status"],
            )
            return self._not_ready_alert(case, f"the case status is '{case['status']}'")

        if not case["evidence"]:
            logger.warning("Case is missing required evidence; generating not-ready alert.")
            return self._not_ready_alert(case, "the required evidence is missing")

        if not self._has_required_evidence(case):
            logger.warning("Case evidence lacks required types; generating not-ready alert.")
            return self._not_ready_alert(
                case, "the case evidence lacks time and distance values"
            )
        logger.info("Evidence validation: OK")

        logger.info(
            "Priority evaluation: severity preserved from case (%s)",
            case["severity"],
        )

        message = self._build_message(case)
        message = maybe_generate(
            "agent_4_message",
            {
                "alert_id": "ALERT001",
                "case_id": case["case_id"],
                "severity": case["severity"],
                "finding_ids": case["finding_ids"],
                "evidence": case["evidence"],
                "recommended_action": case.get("recommended_action") or "Human verification",
            },
            message,
            generator=self.narrative_generator,
        )
        logger.info("Alert construction: message generated")

        alert = {
            "alert_id": "ALERT001",
            "case_id": case["case_id"],
            "severity": case["severity"],
            "title": TITLE,
            "message": message,
            "recommended_action": case.get("recommended_action") or "Human verification",
            "status": READY_STATUS,
        }
        self._validate_alert(alert)
        logger.info(
            "Output validation: OK — %s (status=%s)",
            alert["alert_id"],
            alert["status"],
        )
        return alert

    @staticmethod
    def _validate_case(case: dict) -> None:
        """Reject malformed cases with a clear validation error."""
        case_id = case.get("case_id")
        severity = case.get("severity")
        status = case.get("status")
        finding_ids = case.get("finding_ids")
        summary = case.get("summary")
        evidence = case.get("evidence")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Case is missing a valid 'case_id'")
        if severity not in SUPPORTED_SEVERITIES:
            raise ValueError(
                f"Case {case_id} has invalid 'severity': {severity!r} "
                f"(supported: {SUPPORTED_SEVERITIES})"
            )
        if status not in ("requires_human_review", "not_ready"):
            raise ValueError(f"Case {case_id} has invalid 'status': {status!r}")
        if (
            not isinstance(finding_ids, list)
            or not finding_ids
            or not all(isinstance(f, str) and f for f in finding_ids)
        ):
            raise ValueError(f"Case {case_id} has invalid 'finding_ids'")
        if not isinstance(summary, str) or not summary:
            raise ValueError(f"Case {case_id} is missing a valid 'summary'")
        if not isinstance(evidence, list):
            raise ValueError(f"Case {case_id} has invalid 'evidence'")
        for entry in evidence:
            if (
                not isinstance(entry, dict)
                or set(entry.keys()) != {"type", "value", "unit"}
                or not isinstance(entry["type"], str)
                or not isinstance(entry["unit"], str)
                or not isinstance(entry["value"], (int, float))
                or isinstance(entry["value"], bool)
            ):
                raise ValueError(f"Case {case_id} has malformed evidence entry: {entry!r}")
        confidence = case.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not (0.0 <= confidence <= 1.0)
        ):
            raise ValueError(f"Case {case_id} has invalid 'confidence'")
        recommended_action = case.get("recommended_action")
        if recommended_action is not None and not isinstance(recommended_action, str):
            raise ValueError(f"Case {case_id} has invalid 'recommended_action'")

    @staticmethod
    def _has_required_evidence(case: dict) -> bool:
        """A review alert needs both a time difference and a distance value."""
        entry_types = {entry["type"] for entry in case["evidence"]}
        return "time_difference" in entry_types and "distance" in entry_types

    def _not_ready_alert(self, case: dict, reason: str) -> dict:
        """Build a contract-shaped alert that is explicitly NOT ready."""
        alert = {
            "alert_id": "ALERT001",
            "case_id": case["case_id"],
            "severity": NOT_READY_SEVERITY,
            "title": NOT_READY_TITLE,
            "message": (
                f"No review alert was generated because {reason}. "
                "Human verification is still required."
            ),
            "recommended_action": "Human verification",
            "status": NOT_READY_STATUS,
        }
        self._validate_alert(alert)
        logger.info(
            "Output validation: OK — %s (status=%s)",
            alert["alert_id"],
            alert["status"],
        )
        return alert

    @staticmethod
    def _build_message(case: dict) -> str:
        """Build a concise, factual message from the case's verified evidence."""
        time_entries = [e for e in case["evidence"] if e["type"] == "time_difference"]
        distance_entries = [e for e in case["evidence"] if e["type"] == "distance"]
        if len(time_entries) == 1 and len(distance_entries) == 1:
            time_entry, distance_entry = time_entries[0], distance_entries[0]
            return (
                f"Potential anomaly detected: the referenced transactions were verified "
                f"{time_entry['value']} {time_entry['unit']} apart and "
                f"{distance_entry['value']} {distance_entry['unit']} apart. "
                "Human verification required."
            )
        finding_ids = case["finding_ids"]
        details = "; ".join(
            f"{finding_ids[i]}: {time_entry['value']} {time_entry['unit']} apart and "
            f"{distance_entry['value']} {distance_entry['unit']} apart"
            for i, (time_entry, distance_entry) in enumerate(
                zip(time_entries, distance_entries)
            )
        )
        return (
            f"Potential anomaly detected. Verified evidence: {details}. "
            "Human verification required."
        )

    @staticmethod
    def _validate_alert(alert: dict) -> None:
        """Self-check that the alert satisfies the documented contract."""
        required = set(ALERT_FIELDS)
        if not required.issubset(alert):
            raise ValueError(f"Invalid alert: {alert!r}")
        if alert["status"] not in (READY_STATUS, NOT_READY_STATUS):
            raise ValueError(f"Invalid alert status: {alert['status']!r}")
        if alert["status"] == READY_STATUS:
            if not alert["title"] or not alert["message"]:
                raise ValueError(f"A ready alert needs a title and message: {alert!r}")
            if alert["recommended_action"].lower() not in ("human verification", "human review"):
                raise ValueError(
                    f"A ready alert must recommend human verification: {alert!r}"
                )
