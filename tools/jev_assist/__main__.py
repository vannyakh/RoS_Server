"""python -m tools.jev_assist "question" [--refresh]"""

import argparse
import sys

from tools.jev_assist.client import JevError, ask


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask the jev.ai assistant about the game.")
    parser.add_argument("question")
    parser.add_argument("--refresh", action="store_true", help="skip the local cache")
    args = parser.parse_args()
    try:
        answer, cached = ask(args.question, refresh=args.refresh)
    except JevError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(answer)
    print("(cached)" if cached else "(fresh, saved to .cache/jev)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
