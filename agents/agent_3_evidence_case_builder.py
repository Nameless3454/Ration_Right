"""RationRight — Agent 3: Evidence Case Builder (Phase 4).

Transforms verified findings from Agent 2 into a structured investigation case
(an evidence organizer / case builder, NOT a fraud judge). The case follows the
documented Investigation Case schema in ``RationRight_complete_docs/
data_contract.md``:

    {"case_id", "severity", "status", "finding_ids", "summary",
     "evidence", "confidence", "recommended_action"}

Deterministic rules used by this agent (documented, not fabricated per-case):
- ``status == "requires_human_review"`` when every supplied finding is
  verified, carries calculated evidence, and every referenced transaction is
  present in the supplied source data.
- ``status == "not_ready"`` when any finding is unverified, any verified
  finding is missing calculated evidence, or a referenced transaction is
  missing from the supplied data. No verified case is ever presented from
  unverified input.
- ``severity`` = the shared pattern severity (``high``) for a ready case;
  ``low`` for a not-ready case (no verified evidence to escalate).
- ``confidence`` = 0.9 for a ready case (both anomaly conditions verified
  against calculated evidence); 0.0 for not-ready.
- ``recommended_action`` = "Human verification" (the system never decides
  guilt or punishment).

Agent 2's calculated values are copied into the case unchanged — never
recalculated, altered, or guessed. The narrative is generated deterministically
from actual input facts only (transaction IDs, beneficiary when derivable from
the supplied records, and the verified evidence); interpretation such as
"the beneficiary travelled quickly" is never added.

Input accepts either the documented ``{"findings": [...]}`` shape or a single
``{"finding": {...}}``, each optionally accompanied by ``"transactions": [...]``
used for traceability validation.

Run standalone::

    python3 scripts/run_agent_3.py

Import::

    from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder
"""

from __future__ import annotations

import logging

from agents.llm import maybe_generate
from agents.pattern_config import RAPID_GEOGRAPHIC_SEVERITY

logger = logging.getLogger("rationright.agent_3")

CASE_FIELDS = (
    "case_id",
    "severity",
    "status",
    "finding_ids",
    "summary",
    "evidence",
    "confidence",
    "recommended_action",
)

# Configured deterministic rules (see module docstring).
VERIFIED_CONFIDENCE = 0.9
NOT_READY_CONFIDENCE = 0.0
NOT_READY_SEVERITY = "low"
DEFAULT_SEVERITY = RAPID_GEOGRAPHIC_SEVERITY


class Agent3EvidenceCaseBuilder:
    """Evidence Case Builder: organizes verified findings into a case."""

    def __init__(self, severity: str = DEFAULT_SEVERITY, narrative_generator=None):
        self.severity = severity
        self.narrative_generator = narrative_generator

    def run(self, payload: dict) -> dict:
        """Build one investigation case from verified findings.

        ``payload`` is ``{"findings": [...]}`` or ``{"finding": {...}}``,
        optionally with ``"transactions": [...]`` for traceability checks.
        """
        logger.info("Agent 3 started")
        findings, transactions = self._normalize_input(payload)

        for finding in findings:
            self._validate_finding(finding)
        logger.info(
            "Finding(s) received and validated: %s",
            [f["finding_id"] for f in findings],
        )

        by_id = {
            tx.get("transaction_id"): tx
            for tx in transactions
            if isinstance(tx, dict) and isinstance(tx.get("transaction_id"), str)
        }

        unverified = [f for f in findings if f["status"] != "verified"]
        if unverified:
            logger.warning(
                "Finding(s) are not verified: %s",
                [f["finding_id"] for f in unverified],
            )
            return self._not_ready_case(
                findings,
                "Case is not ready for review: finding(s) "
                f"{', '.join(f['finding_id'] for f in unverified)} are unverified, "
                "so no verified investigation case can be assembled.",
            )

        missing_evidence = [
            f
            for f in findings
            if not isinstance(f.get("evidence"), dict)
            or "time_difference_minutes" not in f["evidence"]
            or "distance_km" not in f["evidence"]
        ]
        if missing_evidence:
            logger.warning(
                "Finding(s) are missing calculated evidence: %s",
                [f["finding_id"] for f in missing_evidence],
            )
            return self._not_ready_case(
                findings,
                "Case is not ready for review: finding(s) "
                f"{', '.join(f['finding_id'] for f in missing_evidence)} are missing "
                "calculated evidence.",
            )

        missing_transactions = []
        for finding in findings:
            for transaction_id in finding["transaction_ids"]:
                if transaction_id not in by_id:
                    missing_transactions.append(transaction_id)
        if missing_transactions:
            logger.warning(
                "Referenced transaction(s) missing from supplied data: %s",
                missing_transactions,
            )
            return self._not_ready_case(
                findings,
                "Case is not ready for review: referenced transaction(s) "
                f"{', '.join(missing_transactions)} are missing from the supplied data.",
            )
        logger.info("Source transactions located: OK")

        # Evidence is copied from Agent 2 unchanged (preservation, not recalculation).
        evidence = []
        for finding in findings:
            evidence.append({
                "type": "time_difference",
                "value": finding["evidence"]["time_difference_minutes"],
                "unit": "minutes",
            })
            evidence.append({
                "type": "distance",
                "value": finding["evidence"]["distance_km"],
                "unit": "km",
            })
        logger.info("Evidence consistency checked: Agent 2 values preserved")

        summary = self._build_summary(findings, by_id)
        summary = maybe_generate(
            "agent_3_summary",
            {
                "case_id": "CASE001",
                "finding_ids": [f["finding_id"] for f in findings],
                "anomaly_ids": [f["anomaly_id"] for f in findings],
                "transaction_ids": sorted(
                    {tid for f in findings for tid in f["transaction_ids"]}
                ),
                "beneficiaries": sorted({
                    by_id[tid]["beneficiary_id"]
                    for f in findings
                    for tid in f["transaction_ids"]
                    if tid in by_id
                    and isinstance(by_id[tid].get("beneficiary_id"), str)
                    and by_id[tid]["beneficiary_id"]
                }),
                "evidence": evidence,
                "severity": self.severity,
                "confidence": VERIFIED_CONFIDENCE,
                "status": "requires_human_review",
            },
            summary,
            generator=self.narrative_generator,
        )
        logger.info("Narrative generated")

        case = {
            "case_id": "CASE001",
            "severity": self.severity,
            "status": "requires_human_review",
            "finding_ids": [f["finding_id"] for f in findings],
            "summary": summary,
            "evidence": evidence,
            "confidence": VERIFIED_CONFIDENCE,
            "recommended_action": "Human verification",
        }
        logger.info("Case assembled")
        self._validate_case(case)
        logger.info(
            "Structured case validated: %s (status=%s)",
            case["case_id"],
            case["status"],
        )
        return case

    @staticmethod
    def _normalize_input(payload: dict):
        """Accept ``{"findings": [...]}`` or ``{"finding": {...}}`` plus
        optional ``"transactions"``. Returns (findings, transactions)."""
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object with 'findings' (or 'finding')")
        findings = payload.get("findings")
        if findings is None:
            single = payload.get("finding")
            if single is None:
                raise ValueError("payload must contain 'findings' (list) or 'finding' (single finding)")
            findings = [single]
        if not isinstance(findings, list) or not findings:
            raise ValueError("payload['findings'] must be a non-empty list of findings")
        transactions = payload.get("transactions", [])
        if not isinstance(transactions, list):
            raise ValueError("payload['transactions'] must be a list")
        return findings, transactions

    @staticmethod
    def _validate_finding(finding) -> None:
        """Reject malformed findings with a clear validation error."""
        if not isinstance(finding, dict):
            raise ValueError("Each finding must be an object")
        finding_id = finding.get("finding_id")
        anomaly_id = finding.get("anomaly_id")
        status = finding.get("status")
        transaction_ids = finding.get("transaction_ids")
        evidence = finding.get("evidence")
        if not isinstance(finding_id, str) or not finding_id:
            raise ValueError("Finding is missing a valid 'finding_id'")
        if not isinstance(anomaly_id, str) or not anomaly_id:
            raise ValueError(f"Finding {finding_id} is missing a valid 'anomaly_id'")
        if status not in ("verified", "unverified"):
            raise ValueError(f"Finding {finding_id} has invalid status: {status!r}")
        if (
            not isinstance(transaction_ids, list)
            or not transaction_ids
            or not all(isinstance(t, str) and t for t in transaction_ids)
        ):
            raise ValueError(f"Finding {finding_id} has invalid 'transaction_ids'")
        if not isinstance(evidence, dict):
            raise ValueError(f"Finding {finding_id} has invalid 'evidence'")
        if status == "verified":
            for key in ("time_difference_minutes", "distance_km"):
                if key in evidence:
                    value = evidence[key]
                    if not isinstance(value, (int, float)) or isinstance(value, bool):
                        raise ValueError(
                            f"Finding {finding_id} has malformed evidence value for '{key}'"
                        )
        evidence_sources = finding.get("evidence_sources")
        if evidence_sources is not None and not isinstance(evidence_sources, list):
            raise ValueError(f"Finding {finding_id} has invalid 'evidence_sources'")

    def _not_ready_case(self, findings: list, summary: str) -> dict:
        """Build a contract-shaped case that is explicitly NOT ready."""
        case = {
            "case_id": "CASE001",
            "severity": NOT_READY_SEVERITY,
            "status": "not_ready",
            "finding_ids": [f["finding_id"] for f in findings],
            "summary": summary,
            "evidence": [],
            "confidence": NOT_READY_CONFIDENCE,
            "recommended_action": "Human verification",
        }
        logger.info("Case assembled (not ready)")
        self._validate_case(case)
        logger.info(
            "Structured case validated: %s (status=%s)",
            case["case_id"],
            case["status"],
        )
        return case

    @staticmethod
    def _build_summary(findings: list, by_id: dict) -> str:
        """Generate a deterministic narrative from actual input facts only."""
        if len(findings) == 1:
            finding = findings[0]
            transaction_ids = finding["transaction_ids"]
            time_diff = finding["evidence"]["time_difference_minutes"]
            distance = finding["evidence"]["distance_km"]
            beneficiaries = sorted({
                by_id[tid]["beneficiary_id"]
                for tid in transaction_ids
                if tid in by_id
                and isinstance(by_id[tid].get("beneficiary_id"), str)
                and by_id[tid]["beneficiary_id"]
            })
            who = f" for beneficiary {', '.join(beneficiaries)}" if beneficiaries else ""
            return (
                f"The referenced transactions {transaction_ids}{who} were recorded "
                f"{time_diff:.2f} minutes apart at locations {distance:.2f} km apart, "
                f"calculated from the supplied transaction timestamps and coordinates. "
                f"Finding {finding['finding_id']} was verified against the configured "
                "rapid-geographic-transaction criteria; this case requires human review."
            )
        details = "; ".join(
            f"finding {f['finding_id']} (anomaly {f['anomaly_id']}) recorded "
            f"{f['evidence']['time_difference_minutes']:.2f} minutes apart at "
            f"{f['evidence']['distance_km']:.2f} km"
            for f in findings
        )
        return (
            f"A case was assembled from verified findings: {details}. Values were "
            "calculated from the supplied transaction timestamps and coordinates; "
            "this case requires human review."
        )

    @staticmethod
    def _validate_case(case: dict) -> None:
        """Self-check that the case satisfies the documented contract."""
        required = set(CASE_FIELDS)
        if not required.issubset(case):
            raise ValueError(f"Invalid case: {case!r}")
        if case["status"] not in ("requires_human_review", "not_ready"):
            raise ValueError(f"Invalid case status: {case['status']!r}")
        if not isinstance(case["finding_ids"], list) or not case["finding_ids"]:
            raise ValueError(f"Case must reference at least one finding: {case!r}")
        if case["status"] == "requires_human_review" and not case["evidence"]:
            raise ValueError(f"A ready case must contain evidence: {case!r}")
        if not isinstance(case["confidence"], (int, float)) or not (0.0 <= case["confidence"] <= 1.0):
            raise ValueError(f"Case confidence must be in [0, 1]: {case!r}")
        for entry in case["evidence"]:
            if (
                not isinstance(entry, dict)
                or set(entry.keys()) != {"type", "value", "unit"}
                or not isinstance(entry["value"], (int, float))
                or isinstance(entry["value"], bool)
            ):
                raise ValueError(f"Case has malformed evidence entry: {entry!r}")
