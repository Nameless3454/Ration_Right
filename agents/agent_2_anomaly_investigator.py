"""RationRight — Agent 2: Anomaly Investigator (Phase 3).

Verifies anomaly candidates produced by Agent 1 against the ACTUAL source
transaction records using deterministic tools. Agent 1 says "this may be
suspicious"; Agent 2 says "I checked those exact transactions and calculated
the evidence."

Everything numerical is deterministic code, never an LLM or a guess:

- transaction lookup against the supplied records;
- timestamp parsing and time-difference calculation;
- haversine geographic distance;
- validation of existence, timestamps, coordinates, and beneficiary consistency;
- threshold evaluation using the shared pattern configuration.

The calculated evidence is NEVER copied from Agent 1's output; it is computed
independently from the source transactions.

Output follows ``RationRight_complete_docs/data_contract.md``. Verified
findings carry computed evidence; failed verifications return status
``unverified`` with empty evidence and a factual explanation of why. The agent
never declares guilt or fraud — a verified finding means "the anomaly candidate
is supported by the supplied data and requires human verification".

Run standalone::

    python3 scripts/run_agent_2.py

Import::

    from agents.agent_2_anomaly_investigator import Agent2AnomalyInvestigator
"""

from __future__ import annotations

import logging
from datetime import datetime

from agents.llm import maybe_generate
from agents.pattern_config import (
    RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
    RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
)
from scripts.validate_dataset import haversine_km, minutes_between

logger = logging.getLogger("rationright.agent_2")

# Thresholds reused from the shared pattern configuration (same as Agent 1).
DEFAULT_MAX_INTERVAL_MINUTES = RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES
DEFAULT_MIN_DISTANCE_KM = RAPID_GEOGRAPHIC_MIN_DISTANCE_KM

FINDING_FIELDS = (
    "finding_id",
    "anomaly_id",
    "status",
    "transaction_ids",
    "evidence",
    "evidence_sources",
    "explanation",
)


class Agent2AnomalyInvestigator:
    """Anomaly Investigator: verifies one anomaly candidate per run."""

    def __init__(
        self,
        max_interval_minutes: float = DEFAULT_MAX_INTERVAL_MINUTES,
        min_distance_km: float = DEFAULT_MIN_DISTANCE_KM,
        narrative_generator=None,
    ):
        if max_interval_minutes <= 0:
            raise ValueError("max_interval_minutes must be positive")
        if min_distance_km <= 0:
            raise ValueError("min_distance_km must be positive")
        self.max_interval_minutes = max_interval_minutes
        self.min_distance_km = min_distance_km
        self.narrative_generator = narrative_generator

    def run(self, payload: dict, finding_id: str = "FIND001") -> dict:
        """Verify one anomaly candidate and return a structured finding.

        ``payload`` must be ``{"anomaly": {...}, "transactions": [...]}``
        following the documented contracts. ``finding_id`` lets the workflow
        assign unique IDs per candidate (default ``FIND001`` preserves
        standalone behavior).
        """
        logger.info("Agent 2 started")
        if not isinstance(finding_id, str) or not finding_id:
            raise ValueError("finding_id must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object with 'anomaly' and 'transactions'")
        anomaly = payload.get("anomaly")
        transactions = payload.get("transactions")
        if not isinstance(anomaly, dict):
            raise ValueError("payload['anomaly'] must be an object")
        if not isinstance(transactions, list):
            raise ValueError("payload['transactions'] must be a list")

        self._validate_candidate(anomaly)
        anomaly_id = anomaly["anomaly_id"]
        transaction_ids = list(anomaly["transaction_ids"])
        expected_beneficiary = anomaly.get("beneficiary_id")
        logger.info("Candidate received: %s (%s) referencing %s",
                    anomaly_id, anomaly.get("anomaly_type", "<unknown>"), transaction_ids)

        # 1. Transaction lookup against the supplied source records.
        by_id = {
            tx.get("transaction_id"): tx
            for tx in transactions
            if isinstance(tx, dict) and isinstance(tx.get("transaction_id"), str)
        }
        missing = [tid for tid in transaction_ids if tid not in by_id]
        if missing:
            logger.warning("Transaction(s) not found: %s", missing)
            return self._unverified(
                anomaly_id,
                transaction_ids,
                "Required transaction data was unavailable: transaction(s) "
                f"{', '.join(missing)} not found in the supplied records.",
                finding_id=finding_id,
            )
        logger.info("Transactions located: %s", transaction_ids)

        # 2. Validate the referenced records.
        records = [by_id[tid] for tid in transaction_ids]
        inspected = [self._inspect_transaction(tx) for tx in records]
        problems = []
        for tid, info in zip(transaction_ids, inspected):
            if not info["timestamp_ok"]:
                problems.append(f"{tid} has a missing/invalid timestamp")
            if not info["coordinates_ok"]:
                problems.append(f"{tid} has missing/invalid coordinates")
            if not info["beneficiary_ok"]:
                problems.append(f"{tid} has a missing/invalid beneficiary_id")
        if problems:
            logger.warning("Validation issue(s) on referenced transactions: %s", problems)
            return self._unverified(
                anomaly_id,
                transaction_ids,
                "Required transaction data was unavailable: " + "; ".join(problems) + ".",
                finding_id=finding_id,
            )

        # 3. Beneficiary consistency.
        beneficiary_ids = {info["beneficiary_id"] for info in inspected}
        if len(beneficiary_ids) != 1:
            logger.warning(
                "Referenced transactions belong to different beneficiaries: %s",
                sorted(beneficiary_ids),
            )
            return self._unverified(
                anomaly_id,
                transaction_ids,
                "The referenced transactions belong to different beneficiaries "
                f"({sorted(beneficiary_ids)}); a same-beneficiary anomaly cannot be verified.",
                finding_id=finding_id,
            )
        actual_beneficiary = next(iter(beneficiary_ids))
        if expected_beneficiary and actual_beneficiary != expected_beneficiary:
            logger.warning(
                "Beneficiary mismatch: candidate expects %s, transactions belong to %s",
                expected_beneficiary,
                actual_beneficiary,
            )
            return self._unverified(
                anomaly_id,
                transaction_ids,
                f"The referenced transactions belong to beneficiary {actual_beneficiary}, "
                f"not the expected {expected_beneficiary}.",
                finding_id=finding_id,
            )
        logger.info("Beneficiary consistency: OK (%s)", actual_beneficiary)

        # 4. Deterministic calculations from the actual source records.
        first, second = records[0], records[1]
        time_difference_minutes = minutes_between(first["timestamp"], second["timestamp"])
        distance_km = haversine_km(
            first["latitude"], first["longitude"],
            second["latitude"], second["longitude"],
        )
        logger.info("Timestamp validation: OK")
        logger.info("Time difference calculated: %.2f minutes", time_difference_minutes)
        logger.info("Coordinates validated: OK")
        logger.info("Geographic distance calculated: %.2f km", distance_km)

        # 5. Threshold evaluation (shared thresholds, inclusive bounds).
        interval_ok = time_difference_minutes <= self.max_interval_minutes
        distance_ok = distance_km >= self.min_distance_km
        logger.info(
            "Thresholds evaluated: interval %.2f <= %g (%s); distance %.2f >= %g (%s)",
            time_difference_minutes, self.max_interval_minutes, interval_ok,
            distance_km, self.min_distance_km, distance_ok,
        )
        if not (interval_ok and distance_ok):
            logger.info("Anomaly conditions NOT satisfied; returning unverified finding.")
            return self._unverified(
                anomaly_id,
                transaction_ids,
                "The referenced transactions do not satisfy the rapid-geographic-"
                f"transaction thresholds (interval {time_difference_minutes:.2f} min "
                f"<= {self.max_interval_minutes:g} min: {interval_ok}; distance "
                f"{distance_km:.2f} km >= {self.min_distance_km:g} km: {distance_ok}).",
                finding_id=finding_id,
            )

        # 6. Verified finding with calculated evidence. The explanation is the
        # optional LLM narrative point; the evidence itself is always the
        # deterministic calculation above, never the LLM's.
        fallback_explanation = (
            f"The referenced transactions {transaction_ids} for beneficiary "
            f"{actual_beneficiary} occurred {time_difference_minutes:.2f} minutes apart "
            f"at {distance_km:.2f} km, satisfying the rapid-geographic-transaction "
            f"thresholds (interval <= {self.max_interval_minutes:g} min, distance >= "
            f"{self.min_distance_km:g} km). Evidence supports the anomaly candidate "
            "and requires human verification."
        )
        finding = {
            "finding_id": finding_id,
            "anomaly_id": anomaly_id,
            "status": "verified",
            "transaction_ids": list(transaction_ids),
            "evidence": {
                "time_difference_minutes": round(time_difference_minutes, 2),
                "distance_km": round(distance_km, 2),
            },
            "evidence_sources": list(transaction_ids),
            "explanation": maybe_generate(
                "agent_2_explanation",
                {
                    "finding_id": finding_id,
                    "anomaly_id": anomaly_id,
                    "anomaly_type": anomaly.get("anomaly_type"),
                    "transaction_ids": list(transaction_ids),
                    "beneficiary_id": actual_beneficiary,
                    "time_difference_minutes": round(time_difference_minutes, 2),
                    "distance_km": round(distance_km, 2),
                    "max_interval_minutes": self.max_interval_minutes,
                    "min_distance_km": self.min_distance_km,
                },
                fallback_explanation,
                generator=self.narrative_generator,
            ),
        }
        self._validate_finding(finding)
        logger.info("Verification result generated: %s (status=%s)",
                    finding["finding_id"], finding["status"])
        return finding

    @staticmethod
    def _validate_candidate(anomaly: dict) -> None:
        """Reject malformed anomaly candidates safely."""
        anomaly_id = anomaly.get("anomaly_id")
        transaction_ids = anomaly.get("transaction_ids")
        if not isinstance(anomaly_id, str) or not anomaly_id:
            raise ValueError("Anomaly candidate is missing a valid 'anomaly_id'")
        if not isinstance(transaction_ids, list) or len(transaction_ids) != 2:
            raise ValueError(
                "Anomaly candidate 'transaction_ids' must be a list of exactly two "
                "transaction IDs"
            )
        if not all(isinstance(tid, str) and tid for tid in transaction_ids):
            raise ValueError("Anomaly candidate 'transaction_ids' must be non-empty strings")

    @staticmethod
    def _inspect_transaction(tx: dict) -> dict:
        """Return per-field validity flags for a referenced transaction."""
        raw_timestamp = tx.get("timestamp")
        timestamp_ok = isinstance(raw_timestamp, str) and bool(raw_timestamp)
        if timestamp_ok:
            try:
                datetime.fromisoformat(raw_timestamp)
            except ValueError:
                timestamp_ok = False

        coordinates_ok = True
        for field, low, high in (("latitude", -90.0, 90.0), ("longitude", -180.0, 180.0)):
            value = tx.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not (low <= value <= high):
                coordinates_ok = False

        beneficiary_id = tx.get("beneficiary_id")
        beneficiary_ok = isinstance(beneficiary_id, str) and bool(beneficiary_id)
        return {
            "timestamp_ok": timestamp_ok,
            "coordinates_ok": coordinates_ok,
            "beneficiary_ok": beneficiary_ok,
            "beneficiary_id": beneficiary_id if beneficiary_ok else None,
        }

    def _unverified(self, anomaly_id: str, transaction_ids: list, explanation: str,
                    finding_id: str = "FIND001") -> dict:
        """Build a contract-compliant unverified finding with no fabricated evidence."""
        finding = {
            "finding_id": finding_id,
            "anomaly_id": anomaly_id,
            "status": "unverified",
            "transaction_ids": list(transaction_ids),
            "evidence": {},
            "evidence_sources": [],
            "explanation": explanation,
        }
        self._validate_finding(finding)
        logger.info("Verification result generated: %s (status=%s)",
                    finding["finding_id"], finding["status"])
        return finding

    @staticmethod
    def _validate_finding(finding: dict) -> None:
        """Self-check that the finding satisfies the output contract."""
        required = set(FINDING_FIELDS)
        if not required.issubset(finding):
            raise ValueError(f"Invalid finding: {finding!r}")
        if finding["status"] not in ("verified", "unverified"):
            raise ValueError(f"Invalid finding status: {finding['status']!r}")
        if finding["status"] == "verified":
            evidence = finding["evidence"]
            if not isinstance(evidence, dict) or "time_difference_minutes" not in evidence or "distance_km" not in evidence:
                raise ValueError(f"Verified finding is missing calculated evidence: {finding!r}")
            if not finding["evidence_sources"]:
                raise ValueError(f"Verified finding is missing evidence sources: {finding!r}")
