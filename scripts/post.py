#!/usr/bin/env python3
"""Stage 5: post one COMMENT review on a PR.

Usage: post.py <work dir> <review.json> [--approve]

review.json: {"body": "<summary>", "comments": [{"path", "line", "body"}]}

Mode comes from repos.json via <work dir>/context.json:
  auto  : posts.
  draft : prints the review and stops, unless --approve is given.
Only lines present in the PR diff can carry an inline comment; anything else
is rejected before posting, so GitHub never gets a request it will refuse.
"""

import json
import re
import sys
from pathlib import Path

from common import run


def diff_lines(diff: str) -> set[tuple[str, int]]:
    """Return (path, line) for every new-side line visible in a unified diff."""
    visible: set[tuple[str, int]] = set()
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
            visible.add((path, line))
            line += 1
    return visible


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    context = json.loads((work / "context.json").read_text())
    review = json.loads(Path(sys.argv[2]).read_text())
    approved = "--approve" in sys.argv

    visible = diff_lines((work / "pr.diff").read_text())
    for comment in review["comments"]:
        if (comment["path"], comment["line"]) not in visible:
            print(f"rejected: {comment['path']}:{comment['line']} is not in the diff")
            return 1

    if context["mode"] == "draft" and not approved:
        print(f"DRAFT for {context['repo']}#{context['number']} (not posted)\n")
        print(review["body"])
        for comment in review["comments"]:
            print(f"\n--- {comment['path']}:{comment['line']}\n{comment['body']}")
        return 0

    payload = {
        "event": "COMMENT",
        "commit_id": context["head_sha"],
        "body": review["body"],
        "comments": [
            {"path": c["path"], "line": c["line"], "side": "RIGHT", "body": c["body"]}
            for c in review["comments"]
        ],
    }
    payload_file = work / "review-payload.json"
    payload_file.write_text(json.dumps(payload))
    out = run(
        [
            "gh", "api", "--method", "POST",
            f"/repos/{context['repo']}/pulls/{context['number']}/reviews",
            "--input", str(payload_file),
        ]
    )
    print(f"posted review {json.loads(out)['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
