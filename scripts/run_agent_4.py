"""RationRight — Agent 4 runner (Phase 5).

Generates a review alert from an Agent 3 investigation case and prints the
structured alert (JSON) to stdout. Execution logs go to stderr.

By default the runner executes the REAL Agent 1, Agent 2, and Agent 3 against
the dataset (no fake agent execution) and passes the resulting case to Agent 4.
Alternatively a saved Agent 3 case can be supplied with ``--case-file``.

Usage::

    python3 scripts/run_agent_4.py
    python3 scripts/run_agent_4.py --case-file case.json
    python3 scripts/run_agent_4.py --quiet
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
from agents.agent_3_evidence_case_builder import Agent3EvidenceCaseBuilder  # noqa: E402
from agents.agent_4_alert_generator import Agent4AlertGenerator  # noqa: E402
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset  # noqa: E402

logger = logging.getLogger("rationright.agent_4")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run RationRight Agent 4 (Alert Generator) on a synthetic dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the synthetic transaction dataset JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--case-file",
        type=Path,
        default=None,
        help="JSON file with one Agent 3 case; if omitted, the real Agent 1, "
             "Agent 2, and Agent 3 are run and the resulting case is used",
    )
    parser.add_argument(
        "--max-interval-minutes",
        type=float,
        default=DEFAULT_MAX_INTERVAL_MINUTES,
        help="Short-interval threshold in minutes (default: %(default)s)",
    )
    parser.add_argument(
        "--min-distance-km",
        type=float,
        default=DEFAULT_MIN_DISTANCE_KM,
        help="Large-distance threshold in km (default: %(default)s)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress execution logs (structured alert is still printed)",
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

        if args.case_file:
            with open(args.case_file, "r", encoding="utf-8") as fh:
                case = json.load(fh)
            logger.info("Loaded case %s from %s",
                        case.get("case_id", "<unknown>"), args.case_file)
        else:
            agent1 = Agent1TransactionAnalyst(
                max_interval_minutes=args.max_interval_minutes,
                min_distance_km=args.min_distance_km,
            )
            anomalies = agent1.run(transactions)["anomalies"]
            if not anomalies:
                logger.error("Agent 1 produced no anomaly candidates; nothing to build from.")
                return 1
            anomaly = anomalies[0]
            logger.info("Using real Agent 1 candidate %s (of %d candidate(s))",
                        anomaly["anomaly_id"], len(anomalies))

            agent2 = Agent2AnomalyInvestigator(
                max_interval_minutes=args.max_interval_minutes,
                min_distance_km=args.min_distance_km,
            )
            finding = agent2.run({"anomaly": anomaly, "transactions": transactions})
            logger.info("Using real Agent 2 finding %s (status=%s)",
                        finding["finding_id"], finding["status"])

            agent3 = Agent3EvidenceCaseBuilder()
            case = agent3.run({"findings": [finding], "transactions": transactions})
            logger.info("Using real Agent 3 case %s (status=%s)",
                        case["case_id"], case["status"])

        agent4 = Agent4AlertGenerator()
        alert = agent4.run(case)
    except ValueError as exc:
        logger.error("Agent 4 rejected the input: %s", exc)
        return 1

    print(json.dumps(alert, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
