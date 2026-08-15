"""RationRight — standalone system health check (Phase 8).

Verifies every component of the demo system without a browser:

    - the synthetic dataset exists, loads, and passes contract validation;
    - all four agents import and instantiate;
    - the complete real workflow (Agent 1 -> 4) runs once on the canonical
      dataset and produces the expected planted-anomaly alert;
    - optionally, a running server's /api/health endpoint (with ``--url``).

Prints a PASS/FAIL line per component and exits 0 only if everything passed.

Usage::

    python3 scripts/health_check.py
    python3 scripts/health_check.py --url http://127.0.0.1:8000
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_dataset import DEFAULT_DATASET_PATH, load_dataset, validate_transactions  # noqa: E402
from workflow import run_workflow  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


def check(name, fn):
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001
        print("  %s  %s: %s" % (FAIL, name, exc))
        return False
    print("  %s  %s%s" % (PASS, name, (" — " + str(detail)) if detail else ""))
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RationRight system health check.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Dataset to verify (default: %(default)s)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Optional base URL of a running server to also check (e.g. http://127.0.0.1:8000)",
    )
    args = parser.parse_args(argv)

    print("RationRight System Health")
    print("-------------------------")

    ok = True

    # Dataset
    ok &= check("Dataset exists", lambda: _require(args.dataset.is_file(), "file not found"))
    ok &= check("Dataset loads", lambda: _load(args.dataset))
    ok &= check("Dataset contract valid", lambda: _validate(args.dataset))

    # Agents
    ok &= check("Agent 1 available", lambda: _agent_ok("agent_1_transaction_analyst", "Agent1TransactionAnalyst"))
    ok &= check("Agent 2 available", lambda: _agent_ok("agent_2_anomaly_investigator", "Agent2AnomalyInvestigator"))
    ok &= check("Agent 3 available", lambda: _agent_ok("agent_3_evidence_case_builder", "Agent3EvidenceCaseBuilder"))
    ok &= check("Agent 4 available", lambda: _agent_ok("agent_4_alert_generator", "Agent4AlertGenerator"))

    # Real workflow smoke run (canonical dataset must yield the planted alert)
    ok &= check("Workflow end-to-end", lambda: _workflow_smoke(args.dataset))

    # Optional live API
    if args.url:
        ok &= check("API reachable (%s)" % args.url, lambda: _api_health(args.url))

    print("-------------------------")
    print("Result: %s" % ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
    return 0 if ok else 1


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)
    return ""


def _load(path):
    dataset = load_dataset(path)
    return "%d transaction(s)" % len(dataset["transactions"])


def _validate(path):
    dataset = load_dataset(path)
    errors = validate_transactions(dataset["transactions"])
    if errors:
        raise RuntimeError("%d error(s), first: %s" % (len(errors), errors[0]))
    return ""


def _agent_ok(module_name, class_name):
    import importlib
    module = importlib.import_module("agents." + module_name)
    getattr(module, class_name)()
    return ""


def _workflow_smoke(path):
    dataset = load_dataset(path)
    result = run_workflow(dataset["transactions"])
    if result["workflow_status"] != "completed":
        raise RuntimeError("workflow status: %s (%s)" % (
            result["workflow_status"], json.dumps(result["errors"])))
    if not result["alerts"]:
        raise RuntimeError("no alert generated on the canonical dataset")
    alert = result["alerts"][0]
    return "alert %s -> case %s" % (alert["alert_id"], alert["case_id"])


def _api_health(base_url):
    url = base_url.rstrip("/") + "/api/health"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "ok":
        raise RuntimeError("health status: %s" % payload.get("status"))
    return "status ok"


if __name__ == "__main__":
    sys.exit(main())
