#!/usr/bin/env python3
"""Stage 2: merge the finders' results into one list.

Usage: merge.py <work dir>

Reads <work dir>/findings-*.json (not the .rejected ones). Two findings on the
same file and the same line, or within 2 lines with the same words in the
title, count as duplicates; the one with the longer evidence is kept.
Writes <work dir>/findings.json.
"""

import json
import re
import sys
from pathlib import Path


def words(title: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", title.lower()))


def same_issue(a: dict, b: dict) -> bool:
    if a["file"] != b["file"]:
        return False
    if a["line"] == b["line"]:
        return True
    if abs(a["line"] - b["line"]) <= 2:
        shared = words(a["title"]) & words(b["title"])
        return len(shared) >= 2
    return False


def merge(findings: list[dict]) -> list[dict]:
    """Drop duplicates, keep the item with the longest evidence, make ids unique."""
    kept: list[dict] = []
    for item in findings:
        for index, other in enumerate(kept):
            if same_issue(item, other):
                if len(item["evidence"]) > len(other["evidence"]):
                    kept[index] = item
                break
        else:
            kept.append(item)
    seen: set[str] = set()
    for item in kept:
        base, count = item["id"], 2
        while item["id"] in seen:
            item["id"] = f"{base}-{count}"
            count += 1
        seen.add(item["id"])
    return kept


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    found: list[dict] = []
    for path in sorted(work.glob("findings-*.json")):
        if not path.name.endswith(".rejected.json"):
            found += json.loads(path.read_text())
    merged = merge(found)
    (work / "findings.json").write_text(json.dumps(merged, indent=2))
    print(f"merged {len(found)} findings into {len(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
