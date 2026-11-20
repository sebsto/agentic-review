#!/usr/bin/env python3
"""Stage 4: classify verified findings as blocking, nit or pre-existing.

Usage: classify.py <work dir>

Reads <work dir>/verified.json. The script works out whether the flagged line
was added by the PR (a "+" line in the diff) and gives that fact to the model.
Writes <work dir>/classified.json: the findings, each with "class" and "reason".
A finding the model skips is classed "nit" so nothing is lost silently.
"""

import json
import re
import sys
from pathlib import Path

from common import ROOT
from find import DEFAULT_MODEL
from llm import ask, extract_json
from validate import check, load_schema


def added_lines(diff: str) -> set[tuple[str, int]]:
    """Return (path, line) for every line the diff adds."""
    added: set[tuple[str, int]] = set()
    path = ""
    line = 0
    for row in diff.splitlines():
        if row.startswith("+++ b/"):
            path = row[6:]
        elif row.startswith("+++ "):
            path = ""
        elif row.startswith("@@"):
            match = re.search(r"\+(\d+)", row)
            line = int(match.group(1)) if match else 0
        elif path and row.startswith("-"):
            continue
        elif path and not row.startswith("\\"):
            if row.startswith("+"):
                added.add((path, line))
            line += 1
    return added


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    verified = json.loads((work / "verified.json").read_text())
    if not verified:
        (work / "classified.json").write_text("[]")
        print("classified 0 findings")
        return 0
    added = added_lines((work / "pr.diff").read_text())
    brief = [
        {
            "finding_id": f["id"], "title": f["title"], "file": f["file"], "line": f["line"],
            "explanation": f["explanation"], "line_added_by_pr": (f["file"], f["line"]) in added,
            "verifier_reasons": [v["reason"] for v in f["votes"] if v["real"]],
        }
        for f in verified
    ]
    system = (ROOT / "prompts" / "classifier.md").read_text()
    user = f"## Diff\n```diff\n{(work / 'pr.diff').read_text()}\n```\n\n## Findings\n{json.dumps(brief, indent=2)}"
    answer = extract_json(ask(DEFAULT_MODEL, system, user))
    schema = load_schema("classified")
    by_id = {a["finding_id"]: a for a in answer if not check(a, schema)}
    out = []
    for f in verified:
        verdict = by_id.get(f["id"], {"class": "nit", "reason": "classifier gave no valid answer"})
        out.append({**f, "class": verdict["class"], "class_reason": verdict["reason"]})
    (work / "classified.json").write_text(json.dumps(out, indent=2))
    counts = {c: sum(1 for f in out if f["class"] == c) for c in ("blocking", "nit", "pre-existing")}
    print(f"classified {len(out)} findings: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
