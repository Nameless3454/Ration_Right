"""RationRight — Agent 1: Transaction Analyst (Phase 2).

Detects the configured MVP suspicious pattern (``rapid_geographic_transaction``)
in synthetic ration-transaction records: the same beneficiary has two
transactions within a short time interval at geographically distant locations.

This agent is fully deterministic and uses **no LLM**: timestamp parsing, time
differences, geographic distance, grouping, filtering, threshold checks, and
validation are all performed by code/tools. The deterministic helpers are shared
with Phase 1 (``scripts.validate_dataset``) so the same definitions of the
pattern are used everywhere. The anomaly explanation is generated from the
actual computed values, never guessed.

MVP thresholds (configurable, documented; inclusive bounds):
    max_interval_minutes = 60  (interval <= threshold counts as "short")
    min_distance_km      = 100 (distance >= threshold counts as "far")

The values are defined centrally in ``agents.pattern_config`` (shared with
Agent 2 and the Phase 1 dataset validator), so the planted pattern
(12 minutes / ~1148 km) is detected and no control case trips.

Output follows ``RationRight_complete_docs/data_contract.md``:

    {"anomalies": [{"anomaly_id", "anomaly_type", "transaction_ids",
                    "beneficiary_id", "reason", "severity"}, ...]}

Missing/invalid data (timestamp, coordinates, beneficiary ID, malformed
records) is never guessed: the affected record is excluded from comparison and
a warning is logged. An empty dataset or a dataset with no matching pair
returns ``{"anomalies": []}``.

Run standalone::

    python3 scripts/run_agent_1.py

Import::

    from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst
"""

from __future__ import annotations

import logging
from datetime import datetime

from agents.pattern_config import (
    RAPID_GEOGRAPHIC_ANOMALY_TYPE,
    RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
    RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
    RAPID_GEOGRAPHIC_SEVERITY,
)
from scripts.validate_dataset import (
    find_suspicious_pairs,
    validate_transactions,
)

logger = logging.getLogger("rationright.agent_1")

# Threshold values live in ``agents.pattern_config`` (single source of truth).
ANOMALY_TYPE = RAPID_GEOGRAPHIC_ANOMALY_TYPE
DEFAULT_MAX_INTERVAL_MINUTES = RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES
DEFAULT_MIN_DISTANCE_KM = RAPID_GEOGRAPHIC_MIN_DISTANCE_KM
DEFAULT_SEVERITY = RAPID_GEOGRAPHIC_SEVERITY

# Fields required by the documented anomaly-candidate contract.
CANDIDATE_FIELDS = (
    "anomaly_id",
    "anomaly_type",
    "transaction_ids",
    "beneficiary_id",
    "reason",
    "severity",
)


class Agent1TransactionAnalyst:
    """Transaction Analyst: turns transaction records into anomaly candidates.

    The agent discovers patterns from the supplied data; no specific
    transaction IDs or anomaly results are hard-coded.
    """

    def __init__(
        self,
        max_interval_minutes: float = DEFAULT_MAX_INTERVAL_MINUTES,
        min_distance_km: float = DEFAULT_MIN_DISTANCE_KM,
        anomaly_type: str = ANOMALY_TYPE,
        severity: str = DEFAULT_SEVERITY,
    ):
        if max_interval_minutes <= 0:
            raise ValueError("max_interval_minutes must be positive")
        if min_distance_km <= 0:
            raise ValueError("min_distance_km must be positive")
        self.max_interval_minutes = max_interval_minutes
        self.min_distance_km = min_distance_km
        self.anomaly_type = anomaly_type
        self.severity = severity

    @staticmethod
    def _record_issue(tx: dict):
        """Return a description of missing/invalid data that prevents safe
        comparison, or ``None`` if the record can be compared."""
        beneficiary_id = tx.get("beneficiary_id")
        if not isinstance(beneficiary_id, str) or not beneficiary_id:
            return "missing/invalid beneficiary_id"
        raw_timestamp = tx.get("timestamp")
        if not isinstance(raw_timestamp, str) or not raw_timestamp:
            return "missing/invalid timestamp"
        try:
            datetime.fromisoformat(raw_timestamp)
        except ValueError:
            return "invalid timestamp"
        for field, low, high in (("latitude", -90.0, 90.0), ("longitude", -180.0, 180.0)):
            value = tx.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not (low <= value <= high):
                return f"missing/invalid {field}"
        return None

    def run(self, transactions) -> dict:
        """Analyze transaction records and return structured anomaly candidates."""
        if not isinstance(transactions, list):
            raise ValueError("transactions must be a list of transaction objects")

        if not transactions:
            logger.info("Empty dataset: no transactions to analyze.")
            return {"anomalies": []}

        validation_errors = validate_transactions(transactions)
        if validation_errors:
            logger.warning("Input validation found %d issue(s):", len(validation_errors))
            for error in validation_errors:
                logger.warning("  %s", error)

        comparable = []
        skipped = []
        for tx in transactions:
            if not isinstance(tx, dict):
                skipped.append(("<malformed>", "record is not an object"))
                continue
            issue = self._record_issue(tx)
            if issue is not None:
                skipped.append((tx.get("transaction_id", "<unknown>"), issue))
                continue
            comparable.append(tx)

        if skipped:
            logger.warning(
                "Skipped %d record(s) that cannot be compared safely: %s",
                len(skipped),
                ", ".join(f"{tx_id} ({issue})" for tx_id, issue in skipped),
            )

        if not comparable:
            logger.warning("No comparable records remain; returning no candidates.")
            return {"anomalies": []}

        by_beneficiary = {}
        for tx in comparable:
            by_beneficiary.setdefault(tx["beneficiary_id"], []).append(tx)
        comparison_count = sum(len(records) * (len(records) - 1) // 2 for records in by_beneficiary.values())
        logger.info(
            "Evaluated %d same-beneficiary pair comparison(s) across %d beneficiary group(s) (%d record(s))",
            comparison_count,
            len(by_beneficiary),
            len(comparable),
        )

        pairs = find_suspicious_pairs(
            comparable,
            short_interval_minutes=self.max_interval_minutes,
            large_distance_km=self.min_distance_km,
        )
        logger.info(
            "Rule '%s' (interval <= %g min, distance >= %g km) matched %d pair(s)",
            self.anomaly_type,
            self.max_interval_minutes,
            self.min_distance_km,
            len(pairs),
        )
        for pair in pairs:
            logger.info(
                "  Triggered for %s (beneficiary %s): %s minutes, %s km",
                pair["transaction_ids"],
                pair["beneficiary_id"],
                pair["time_difference_minutes"],
                pair["distance_km"],
            )

        candidates = self._build_candidates(pairs)
        self._validate_candidates(candidates)
        logger.info(
            "Generated %d anomaly candidate(s): %s",
            len(candidates),
            [candidate["anomaly_id"] for candidate in candidates],
        )
        return {"anomalies": candidates}

    def _build_candidates(self, pairs: list) -> list:
        """Convert matched pairs into contract-compliant anomaly candidates."""
        candidates = []
        for index, pair in enumerate(pairs, start=1):
            candidates.append(
                {
                    "anomaly_id": f"ANOM{index:03d}",
                    "anomaly_type": self.anomaly_type,
                    "transaction_ids": list(pair["transaction_ids"]),
                    "beneficiary_id": pair["beneficiary_id"],
                    "reason": (
                        f"Two transactions for beneficiary {pair['beneficiary_id']} occurred "
                        f"{pair['time_difference_minutes']:.1f} minutes apart at locations "
                        f"{pair['distance_km']:.2f} km apart, meeting the "
                        f"rapid-geographic-transaction rule (interval <= "
                        f"{self.max_interval_minutes:g} min, distance >= "
                        f"{self.min_distance_km:g} km)."
                    ),
                    "severity": self.severity,
                }
            )
        return candidates

    @staticmethod
    def _validate_candidates(candidates: list) -> None:
        """Self-check that every candidate satisfies the output contract."""
        required = set(CANDIDATE_FIELDS)
        for candidate in candidates:
            if not isinstance(candidate, dict) or not required.issubset(candidate):
                raise ValueError(f"Invalid anomaly candidate: {candidate!r}")
            if not candidate["transaction_ids"]:
                raise ValueError(f"Anomaly candidate has empty transaction_ids: {candidate!r}")
            if not isinstance(candidate["reason"], str) or not candidate["reason"]:
                raise ValueError(f"Anomaly candidate has empty reason: {candidate!r}")
