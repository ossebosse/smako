"""Register a municipality for the ordinary shared refresh operation."""
import argparse
import json

from grocery_data.app.services.municipal_rollout import add_municipality, refresh_scopes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--municipality", required=True)
    add.add_argument("--postal-code", required=True, help="Unique five-digit build scope; municipality controls store membership")
    add.add_argument("--dry-run", action="store_true")
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
    if args.dry_run:
        result = add_municipality(args.municipality, args.postal_code)
    else:
        from deploy.scripts.run_daily_refresh import _operations_lock
        with _operations_lock():
            result = add_municipality(args.municipality, args.postal_code, persist=True)
    print(json.dumps({"persisted": not args.dry_run, "registry": result,
                      "price_collection": "next_ordinary_refresh", "publication": "not_yet_verified"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
