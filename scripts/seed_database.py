"""RationRight — seed the normalized database with the synthetic dataset.

Creates the Phase 2 schema (if needed) and imports the existing Phase 1
synthetic dataset into it, recording provenance (DataSource + DataImport) so
every row is traceable to its source. Deterministic and idempotent: re-running
resets only the synthetic source's rows and re-imports them.

Usage::

    python3 scripts/seed_database.py
    python3 scripts/seed_database.py --db data/rationright.db
    python3 scripts/seed_database.py --dataset data/synthetic/transactions.json
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import DEFAULT_DB_PATH, seed_database  # noqa: E402
from scripts.validate_dataset import DEFAULT_DATASET_PATH  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Create/seed the RationAI database with the synthetic dataset."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Database file path (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Synthetic dataset JSON to import (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    try:
        summary = seed_database(db_path=args.db, dataset_path=args.dataset)
    except Exception as exc:  # noqa: BLE001
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    print("Database:  %s" % args.db)
    print("Source:    %s" % database_source_label())
    print("Imported:  %d beneficiary(ies), %d transaction(s)" % (
        summary["beneficiaries"], summary["transactions"]))
    print("DataImport id: %d (traceable source of all rows)" % summary["data_import_id"])
    return 0


def database_source_label() -> str:
    from database import SYNTHETIC_SOURCE_NAME
    return SYNTHETIC_SOURCE_NAME


if __name__ == "__main__":
    sys.exit(main())
