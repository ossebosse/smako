"""Register a municipality for the ordinary shared refresh operation."""
import argparse
import json
import shutil
from pathlib import Path

from grocery_data.app.services.municipal_rollout import add_municipality, refresh_scopes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--municipality", required=True)
    add.add_argument("--postal-code", required=True, help="Unique five-digit build scope; municipality controls store membership")
    add.add_argument("--dry-run", action="store_true")
    add.add_argument("--capacity-evidence", type=Path, help="Measured complete pilot JSON, required for a new active municipality")
    capacity = commands.add_parser("capacity")
    capacity.add_argument("--municipality", required=True)
    capacity.add_argument("--postal-code", required=True)
    capacity.add_argument("--capacity-evidence", type=Path, required=True)
    commands.add_parser("list")
    commands.add_parser("relay-scopes")
    args = parser.parse_args(argv)
    if args.command in {"list", "relay-scopes"}:
        scopes = refresh_scopes()
        if args.command == "relay-scopes":
            scopes = [{"municipality_code": s["municipality_code"], "city": s["city"]}
                      for s in scopes if "willys" in s["sources"]]
        print(json.dumps({"municipalities": scopes}, ensure_ascii=False))
        return 0
    if args.command == 'capacity':
        report = _capacity(args)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['status'] == 'PASS' else 2
    if args.dry_run:
        result = add_municipality(args.municipality, args.postal_code)
    else:
        from deploy.scripts.run_daily_refresh import _operations_lock
        with _operations_lock():
            from grocery_data.app.services.municipal_rollout import read_registry
            if args.municipality not in read_registry().get('refresh_scopes', {}):
                report = _capacity(args)
                if report['status'] != 'PASS':
                    print(json.dumps(report, ensure_ascii=False))
                    return 2
            result = add_municipality(args.municipality, args.postal_code, persist=True)
    print(json.dumps({"persisted": not args.dry_run, "registry": result,
                      "price_collection": "next_ordinary_refresh", "publication": "not_yet_verified"}, ensure_ascii=False))
    return 0


def _capacity(args):
    from grocery_data.app.services.municipal_capacity import capacity_report
    from grocery_data.app.services.municipal_rollout import SOURCES, registry_path

    evidence = json.loads(args.capacity_evidence.read_bytes()) if args.capacity_evidence else {}
    return capacity_report(evidence, municipality=args.municipality, postal_code=args.postal_code,
                           sources=SOURCES, free_bytes=shutil.disk_usage(registry_path().parent).free)


if __name__ == "__main__":
    raise SystemExit(main())
