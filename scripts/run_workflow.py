"""RationRight — full multi-agent workflow CLI (Phase 6).

Executes the complete real workflow:

    Dataset -> Agent 1 -> Agent 2 -> Agent 3 -> Agent 4

and prints the final structured result (JSON) to stdout. Execution logs go to
stderr, so stdout stays clean JSON.

Usage::

    python3 scripts/run_workflow.py
    python3 scripts/run_workflow.py --dataset data/synthetic/transactions.json
    python3 scripts/run_workflow.py --max-interval-minutes 60 --min-distance-km 100
    python3 scripts/run_workflow.py --quiet
"""

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.agent_2_anomaly_investigator import (  # noqa: E402
    DEFAULT_MAX_INTERVAL_MINUTES,
    DEFAULT_MIN_DISTANCE_KM,
)
from agents.env import load_env_file  # noqa: E402
from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset  # noqa: E402
from workflow import run_workflow  # noqa: E402

logger = logging.getLogger("rationright.workflow")


def main(argv=None) -> int:
    # Load local secrets (e.g. OPENAI_API_KEY) from the git-ignored .env file.
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Run the complete RationRight multi-agent workflow (Agent 1 -> 4)."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to the synthetic transaction dataset JSON (default: %(default)s)",
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
        help="Suppress execution logs (structured result is still printed)",
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
        result = run_workflow(
            transactions,
            max_interval_minutes=args.max_interval_minutes,
            min_distance_km=args.min_distance_km,
        )
    except ValueError as exc:
        logger.error("Workflow rejected the input: %s", exc)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
