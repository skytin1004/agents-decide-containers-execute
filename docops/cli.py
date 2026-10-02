import argparse
import json
from pathlib import Path
import sys

from .contracts import InvalidRequest, RequestConflict, WorkRequest
from .local import LocalStore


def main():
    parser = argparse.ArgumentParser(description="Local rehearsal of the deterministic work boundary; no model or Azure calls.")
    parser.add_argument("--state", type=Path, default=Path(".artifacts/local"))
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit")
    submit.add_argument("file", type=Path)
    run = commands.add_parser("work")
    run.add_argument("--fail-once", action="store_true")
    status = commands.add_parser("status")
    status.add_argument("request_id")
    export = commands.add_parser("export")
    export.add_argument("request_id")
    commands.add_parser("demo")
    args = parser.parse_args()
    store = LocalStore(args.state)
    try:
        if args.command == "submit":
            result = store.submit(WorkRequest.parse(json.loads(args.file.read_text(encoding="utf-8"))))
        elif args.command == "work":
            result = store.run_one(args.fail_once)
        elif args.command == "status":
            row = store.get(args.request_id)
            result = {k: row[k] for k in ("id", "status", "attempts", "error")} if row else {"status": "not_found"}
        elif args.command == "export":
            result = {"report_directory": str(store.export(args.request_id))}
        else:
            request = WorkRequest.parse({"schema_version": 1, "request_id": "docops-demo-001",
                                         "repository_id": "docs-fixture-v1",
                                         "actions": ["check_links", "check_translation_drift"]})
            print("LOCAL REHEARSAL: scripted decision; deterministic worker; no Azure or LLM call")
            print(json.dumps(store.submit(request)))
            existing = store.get(request.request_id)
            if existing["status"] != "completed":
                print(json.dumps(store.run_one(), indent=2))
            print(json.dumps(store.submit(request)))
            result = {"report_directory": str(store.export(request.request_id))}
        print(json.dumps(result, indent=2))
    except (InvalidRequest, RequestConflict, ValueError) as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
