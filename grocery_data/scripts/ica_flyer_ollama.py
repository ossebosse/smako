"""Local-only stdin/stdout smako-public-flyer-page-v1 process."""
import json
import sys

from grocery_data.app.services.ica_flyer_ollama import Settings, VisionBlocked, analyze


def main():
    try:
        result = analyze(json.load(sys.stdin), Settings.from_env())
    except Exception as exc:  # noqa: BLE001 - safe protocol error, never remote bodies
        print(json.dumps({'status': 'blocked', 'reason': str(exc) if isinstance(exc, VisionBlocked)
                          else type(exc).__name__, 'external_fallback': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
