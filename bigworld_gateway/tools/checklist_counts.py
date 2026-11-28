"""Recount docs/RESTORATION_CHECKLIST.md and rewrite its Total/Passed/Failed/Pending header.

Usage: python tools/checklist_counts.py [--check]
--check only prints the counts and exits 1 if the header is out of date.
"""
import re
import sys
from collections import Counter
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "docs" / "RESTORATION_CHECKLIST.md"
ITEM = re.compile(r"^- \[( |x)\] (\d\d\.\d\d) .+? — (PASS|FAIL|PARTIAL|CODED|CLIENT|NOT TESTED)\b", re.M)


def main():
    text = DOC.read_text(encoding="utf-8")
    items = ITEM.findall(text)
    ids = [i for _, i, _ in items]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    bad_box = [i for box, i, s in items if (box == "x") != (s == "PASS")]
    if dupes or bad_box:
        sys.exit(f"duplicate ids: {dupes}; checkbox/status mismatch: {bad_box}")
    st = Counter(s for _, _, s in items)
    passed, failed = st["PASS"], st["FAIL"]
    header = (f"Total: {len(items)}\nPassed: {passed}\nFailed: {failed}\n"
              f"Pending: {len(items) - passed - failed}")
    new = re.sub(r"Total: \d+\nPassed: \d+\nFailed: \d+\nPending: \d+", header, text, count=1)
    print(header.replace("\n", " | "), "|", dict(st))
    if "--check" in sys.argv:
        sys.exit(0 if new == text else 1)
    DOC.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
