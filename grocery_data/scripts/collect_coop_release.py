"""Explicit candidate-only entry point for the existing physical Coop collector."""
import argparse
import asyncio
import json
from pathlib import Path

from app.providers.coop_municipality_offers import approved_inventory

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.scripts.collect_coop_physical_offers import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enabled', action='store_true', required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--operation-database', type=Path, required=True)
    parser.add_argument('--operation-universe-root', type=Path, required=True)
    parser.add_argument('--store-id', action='append', default=[])
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_bytes())
    approved = approved_inventory(inventory)
    selected = set(args.store_id) if args.store_id else set(approved)
    if not selected or not selected.issubset(approved):
        parser.error('only explicitly verified municipality stores are allowed')
    output = args.output.resolve()
    if (output.exists() or output.is_relative_to(args.operation_database.resolve().parent)
            or output.is_relative_to(args.operation_universe_root.resolve())):
        parser.error('output must be a new isolated directory outside production source roots')
    lock = production_refresh_lock_path(args.operation_database, args.operation_universe_root)
    with RefreshRunLock(lock):
        report = asyncio.run(collect(inventory, selected, output))
    print(json.dumps({'production_activation': False, 'selected': sorted(selected),
                      'successful': sum(s['status'] == 'partial_candidate' for s in report['stores']),
                      'seconds': report['runtime_seconds']}))
    if any(s['status'] != 'partial_candidate' for s in report['stores']):
        raise SystemExit(1)  # Retain partial evidence; never report a failed batch as success.


if __name__ == '__main__':
    main()
