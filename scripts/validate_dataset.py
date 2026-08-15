"""RationRight — Phase 1: synthetic dataset validation.

Validates ``data/synthetic/transactions.json`` against the documented
transaction contract (RationRight_complete_docs/data_contract.md) and
verifies the deliberately planted rapid-geographic-transaction pattern.

Standalone run::

    python scripts/validate_dataset.py

Test suite::

    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Allow standalone execution (``python3 scripts/validate_dataset.py``) to
# import the shared pattern configuration from the project root.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Rapid-geographic-transaction pattern thresholds, shared with the agents via
# ``agents.pattern_config`` so no threshold values are duplicated.
from agents.pattern_config import (  # noqa: E402
    RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES as SHORT_INTERVAL_MINUTES,
    RAPID_GEOGRAPHIC_MIN_DISTANCE_KM as LARGE_DISTANCE_KM,
)

DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "transactions.json"

REQUIRED_FIELDS = (
    "transaction_id",
    "beneficiary_id",
    "timestamp",
    "latitude",
    "longitude",
    "ration_type",
    "quantity",
)

RATION_TYPES = ("rice", "wheat", "sugar", "kerosene")

# The deliberately planted suspicious pair (documented in data/synthetic/README.md).
PLANTED_ANOMALY_IDS = ("TX001", "TX002")


def load_dataset(path: Path = DEFAULT_DATASET_PATH) -> dict:
    """Load the synthetic dataset JSON file and return the parsed content."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_transactions(transactions: list) -> list:
    """Return a list of validation error strings; an empty list means valid."""
    errors: list = []
    seen_ids: set = set()
    for index, tx in enumerate(transactions):
        prefix = f"record[{index}]"
        if not isinstance(tx, dict):
            errors.append(f"{prefix}: transaction must be an object, got {type(tx).__name__}")
            continue

        for field in REQUIRED_FIELDS:
            if field not in tx:
                errors.append(f"{prefix}: missing required field '{field}'")

        transaction_id = tx.get("transaction_id")
        if not isinstance(transaction_id, str) or not transaction_id:
            errors.append(f"{prefix}: transaction_id must be a non-empty string")
        elif transaction_id in seen_ids:
            errors.append(f"{prefix}: duplicate transaction_id '{transaction_id}'")
        if isinstance(transaction_id, str):
            seen_ids.add(transaction_id)

        beneficiary_id = tx.get("beneficiary_id")
        if not isinstance(beneficiary_id, str) or not beneficiary_id:
            errors.append(f"{prefix}: beneficiary_id must be a non-empty string")

        raw_timestamp = tx.get("timestamp")
        if not isinstance(raw_timestamp, str) or not raw_timestamp:
            errors.append(f"{prefix}: timestamp must be a non-empty string")
        else:
            try:
                datetime.fromisoformat(raw_timestamp)
            except ValueError:
                errors.append(f"{prefix}: timestamp '{raw_timestamp}' is not valid ISO-8601")

        latitude = tx.get("latitude")
        if not isinstance(latitude, (int, float)) or isinstance(latitude, bool) or not (-90 <= latitude <= 90):
            errors.append(f"{prefix}: latitude must be a number in [-90, 90]")
        longitude = tx.get("longitude")
        if not isinstance(longitude, (int, float)) or isinstance(longitude, bool) or not (-180 <= longitude <= 180):
            errors.append(f"{prefix}: longitude must be a number in [-180, 180]")

        quantity = tx.get("quantity")
        if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity <= 0:
            errors.append(f"{prefix}: quantity must be a positive number")

        ration_type = tx.get("ration_type")
        if ration_type not in RATION_TYPES:
            errors.append(f"{prefix}: ration_type '{ration_type}' not in {RATION_TYPES}")

    return errors


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometres.

    Deterministic code calculation; never estimated by an LLM.
    """
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def minutes_between(timestamp_a: str, timestamp_b: str) -> float:
    """Absolute time difference in minutes between two ISO-8601 timestamps."""
    dt_a = datetime.fromisoformat(timestamp_a)
    dt_b = datetime.fromisoformat(timestamp_b)
    return abs((dt_b - dt_a).total_seconds()) / 60.0


def find_suspicious_pairs(
    transactions: list,
    short_interval_minutes: float = SHORT_INTERVAL_MINUTES,
    large_distance_km: float = LARGE_DISTANCE_KM,
) -> list:
    """Find same-beneficiary pairs meeting the rapid-geographic pattern.

    Returns a list of dicts with transaction_ids, beneficiary_id,
    time_difference_minutes, and distance_km.
    """
    by_beneficiary: dict = {}
    for tx in transactions:
        by_beneficiary.setdefault(tx["beneficiary_id"], []).append(tx)

    pairs: list = []
    for beneficiary_id, records in by_beneficiary.items():
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a, b = records[i], records[j]
                delta_minutes = minutes_between(a["timestamp"], b["timestamp"])
                distance_km = haversine_km(
                    a["latitude"], a["longitude"], b["latitude"], b["longitude"]
                )
                if delta_minutes <= short_interval_minutes and distance_km >= large_distance_km:
                    pairs.append(
                        {
                            "transaction_ids": sorted([a["transaction_id"], b["transaction_id"]]),
                            "beneficiary_id": beneficiary_id,
                            "time_difference_minutes": round(delta_minutes, 2),
                            "distance_km": round(distance_km, 2),
                        }
                    )
    return pairs


def verify_planted_anomaly(transactions: list, planted_ids: tuple = PLANTED_ANOMALY_IDS) -> dict:
    """Verify the planted pair exists and satisfies the intended pattern.

    Returns a report dict; ``pattern_satisfied`` is True only when the pair
    shares a beneficiary, is within the short interval, and is far apart.
    """
    by_id = {tx["transaction_id"]: tx for tx in transactions}
    missing = [tx_id for tx_id in planted_ids if tx_id not in by_id]
    if missing:
        return {"present": False, "missing_transactions": missing}

    a, b = by_id[planted_ids[0]], by_id[planted_ids[1]]
    time_difference_minutes = minutes_between(a["timestamp"], b["timestamp"])
    distance_km = haversine_km(
        a["latitude"], a["longitude"], b["latitude"], b["longitude"]
    )
    conditions = {
        "same_beneficiary": a["beneficiary_id"] == b["beneficiary_id"],
        "short_time_interval": time_difference_minutes <= SHORT_INTERVAL_MINUTES,
        "large_geographic_distance": distance_km >= LARGE_DISTANCE_KM,
    }
    return {
        "present": True,
        "transaction_ids": list(planted_ids),
        "beneficiary_id": a["beneficiary_id"],
        "time_difference_minutes": round(time_difference_minutes, 2),
        "distance_km": round(distance_km, 2),
        "conditions": conditions,
        "pattern_satisfied": all(conditions.values()),
    }


def main(path: Path = DEFAULT_DATASET_PATH) -> int:
    """Run all dataset checks and print a report. Returns exit code."""
    dataset = load_dataset(path)
    transactions = dataset["transactions"]
    metadata = dataset.get("metadata", {})

    print(f"Dataset:        {path}")
    print(f"Label:          {metadata.get('label', '<missing>')}")
    print(f"Version:        {metadata.get('version', '<missing>')}")
    print(f"Records:        {len(transactions)}")
    print(f"Beneficiaries:  {len({tx['beneficiary_id'] for tx in transactions})}")
    print(f"Ration types:   {sorted({tx['ration_type'] for tx in transactions})}")

    errors = validate_transactions(transactions)
    print(f"\nSchema validation: {'PASSED' if not errors else 'FAILED'}")
    for error in errors:
        print(f"  - {error}")

    report = verify_planted_anomaly(transactions)
    print("\nPlanted anomaly verification:")
    print(f"  Present:           {report['present']}")
    if report["present"]:
        print(f"  Transaction IDs:   {', '.join(report['transaction_ids'])}")
        print(f"  Beneficiary:       {report['beneficiary_id']}")
        print(f"  Time difference:   {report['time_difference_minutes']} minutes")
        print(f"  Distance:          {report['distance_km']} km")
        print(f"  Conditions met:    {report['conditions']}")
        print(f"  Pattern satisfied: {report['pattern_satisfied']}")

    pairs = find_suspicious_pairs(transactions)
    print("\nDeterministic scan for rapid-geographic pairs (thresholds "
          f"{SHORT_INTERVAL_MINUTES} min / {LARGE_DISTANCE_KM} km):")
    if not pairs:
        print("  (none found)")
    for pair in pairs:
        print(
            f"  {pair['transaction_ids']} beneficiary={pair['beneficiary_id']} "
            f"interval={pair['time_difference_minutes']} min "
            f"distance={pair['distance_km']} km"
        )

    exactly_planted = (
        len(pairs) == 1 and pairs[0]["transaction_ids"] == sorted(PLANTED_ANOMALY_IDS)
    )
    print(f"\nExactly the planted pair only: {'YES' if exactly_planted else 'NO'}")

    passed = (
        not errors
        and report.get("present", False)
        and report.get("pattern_satisfied", False)
        and exactly_planted
    )
    print(f"\nRESULT: {'PASSED' if passed else 'FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
