"""stdin/stdout smako-public-flyer-page-v1 worker, or safe access preflight."""
import argparse
import json
import sys

from grocery_data.app.services.ica_flyer_openai import Settings, VisionBlocked, analyze, preflight


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--check-access',action='store_true',help='GET model metadata only; no billable generation')
    args=parser.parse_args()
    try:
        settings=Settings.from_env()
        result=preflight(settings,check_access=args.check_access) if args.preflight else analyze(json.load(sys.stdin),settings)
    except Exception as exc:  # noqa: BLE001 - never expose keys or remote error bodies
        print(json.dumps({'status':'blocked','reason':str(exc) if isinstance(exc,VisionBlocked) else type(exc).__name__}),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
