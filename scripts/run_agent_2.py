"""RationRight — Agent 2 runner (Phase 3).

Verifies an anomaly candidate against source transaction records and prints the
structured finding (JSON) to stdout. Execution logs go to stderr.

By default the runner executes the REAL Agent 1 against the dataset (no fake
agent execution) and verifies its first anomaly candidate. Alternatively a
saved Agent 1-style candidate can be supplied with ``--anomaly-file``.

Usage::

    python3 scripts/run_agent_2.py
    python3 scripts/run_agent_2.py --anomaly-file anomaly_candidate.json
    python3 scripts/run_agent_2.py --max-interval-minutes 60 --min-distance-km 100
    python3 scripts/run_agent_2.py --quiet
"""

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.agent_1_transaction_analyst import Agent1TransactionAnalyst  # noqa: E402
from agents.agent_2_anomaly_investigator import (  # noqa: E402
    DEFAULT_MAX_INTERVAL_MINUTES,
    DEFAULT_MIN_DISTANCE_KM,
    Agent2AnomalyInvestigator,
)
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset  # noqa: E402

logger = logging.getLogger("rationright.agent_2")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run RationRight Agent 2 (Anomaly Investigator) on a synthetic dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the synthetic transaction dataset JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--anomaly-file",
        type=Path,
        default=None,
        help="JSON file with one anomaly candidate (or an Agent 1 result "
             "{\"anomalies\": [...]}); if omitted, the real Agent 1 is run "
             "and its first candidate is verified",
    )
    parser.add_argument(
        "--max-interval-minutes",
        type=float,
        default=DEFAULT_MAX_INTERVAL_MINUTES,
        help="Short-interval threshold in minutes, inclusive (default: %(default)s)",
    )
    parser.add_argument(
        "--min-distance-km",
        type=float,
        default=DEFAULT_MIN_DISTANCE_KM,
        help="Large-distance threshold in km, inclusive (default: %(default)s)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress execution logs (structured finding is still printed)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.ERROR if args.quiet else logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    try:
        dataset = load_dataset(args.dataset)
        transactions = dataset["transactions"]
        logger.info("Loaded %d transaction(s) from %s", len(transactions), args.dataset)

        if args.anomaly_file:
            with open(args.anomaly_file, "r", encoding="utf-8") as fh:
                anomaly_payload = json.load(fh)
            if isinstance(anomaly_payload, dict) and "anomalies" in anomaly_payload:
                anomalies = anomaly_payload["anomalies"]
                if not anomalies:
                    logger.error("Anomaly file contains no anomaly candidates.")
                    return 1
                anomaly = anomalies[0]
            elif isinstance(anomaly_payload, dict):
                anomaly = anomaly_payload
            else:
                logger.error("Anomaly file must contain an anomaly candidate object.")
                return 1
            logger.info("Loaded anomaly candidate %s from %s",
                        anomaly.get("anomaly_id", "<unknown>"), args.anomaly_file)
        else:
            agent1 = Agent1TransactionAnalyst(
                max_interval_minutes=args.max_interval_minutes,
                min_distance_km=args.min_distance_km,
            )
            agent1_result = agent1.run(transactions)
            anomalies = agent1_result["anomalies"]
            if not anomalies:
                logger.error("Agent 1 produced no anomaly candidates; nothing to verify.")
                return 1
            anomaly = anomalies[0]
            logger.info("Using real Agent 1 candidate %s (of %d candidate(s))",
                        anomaly["anomaly_id"], len(anomalies))

        agent2 = Agent2AnomalyInvestigator(
            max_interval_minutes=args.max_interval_minutes,
            min_distance_km=args.min_distance_km,
        )
        finding = agent2.run({"anomaly": anomaly, "transactions": transactions})
    except ValueError as exc:
        logger.error("Agent 2 rejected the input: %s", exc)
        return 1

    print(json.dumps(finding, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
