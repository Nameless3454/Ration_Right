"""RationRight — Agent 3 runner (Phase 4).

Builds an investigation case from verified findings and prints the structured
case (JSON) to stdout. Execution logs go to stderr.

By default the runner executes the REAL Agent 1 and Agent 2 against the
dataset (no fake agent execution) and passes the resulting finding plus the
source transactions to Agent 3. Alternatively a saved Agent 2 finding can be
supplied with ``--finding-file``.

Usage::

    python3 scripts/run_agent_3.py
    python3 scripts/run_agent_3.py --finding-file finding.json
    python3 scripts/run_agent_3.py --quiet
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
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset  # noqa: E402

logger = logging.getLogger("rationright.agent_3")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run RationRight Agent 3 (Evidence Case Builder) on a synthetic dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the synthetic transaction dataset JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--finding-file",
        type=Path,
        default=None,
        help="JSON file with one Agent 2 finding (or {\"findings\": [...]}); "
             "if omitted, the real Agent 1 and Agent 2 are run and the "
             "resulting finding is used",
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
        help="Suppress execution logs (structured case is still printed)",
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

        if args.finding_file:
            with open(args.finding_file, "r", encoding="utf-8") as fh:
                finding_payload = json.load(fh)
            if isinstance(finding_payload, dict) and "findings" in finding_payload:
                findings = finding_payload["findings"]
            elif isinstance(finding_payload, dict) and "finding" in finding_payload:
                findings = [finding_payload["finding"]]
            elif isinstance(finding_payload, dict):
                findings = [finding_payload]
            else:
                logger.error("Finding file must contain a finding object or list.")
                return 1
            logger.info("Loaded %d finding(s) from %s", len(findings), args.finding_file)
        else:
            agent1 = Agent1TransactionAnalyst(
                max_interval_minutes=args.max_interval_minutes,
                min_distance_km=args.min_distance_km,
            )
            anomalies = agent1.run(transactions)["anomalies"]
            if not anomalies:
                logger.error("Agent 1 produced no anomaly candidates; nothing to build a case from.")
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
            findings = [finding]

        agent3 = Agent3EvidenceCaseBuilder()
        case = agent3.run({"findings": findings, "transactions": transactions})
    except ValueError as exc:
        logger.error("Agent 3 rejected the input: %s", exc)
        return 1

    print(json.dumps(case, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
