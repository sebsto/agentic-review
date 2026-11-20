#!/usr/bin/env python3
"""Stage 5a: turn classified findings into a review for post.py.

Usage: report.py <work dir> <review.json out>

Blocking and nit findings become inline comments, with a suggestion block when
the finding has a concrete fix. Pre-existing findings go in the summary only.
The summary starts with the counts and says plainly when nothing was found.
"""

import json
import sys
from pathlib import Path


def comment_body(finding: dict) -> str:
    label = "Blocking" if finding["class"] == "blocking" else "Nit"
    text = f"**{label}: {finding['title']}**\n\n{finding['explanation']}"
    if finding.get("suggested_fix"):
        text += f"\n\n```suggestion\n{finding['suggested_fix']}\n```"
    return text


def build_review(findings: list[dict], head_sha: str = "") -> dict:
    blocking = [f for f in findings if f["class"] == "blocking"]
    nits = [f for f in findings if f["class"] == "nit"]
    older = [f for f in findings if f["class"] == "pre-existing"]
    if not findings:
        body = "No issues found."
    else:
        body = f"{len(blocking)} blocking, {len(nits)} nit, {len(older)} pre-existing."
        if blocking:
            body += "\n\nBlocking:\n" + "\n".join(f"- `{f['file']}:{f['line']}` {f['title']}" for f in blocking)
        if older:
            body += "\n\nAlready in the code before this PR (not for this PR to fix):\n" + "\n".join(
                f"- `{f['file']}:{f['line']}` {f['title']}" for f in older
            )
    comments = [
        {"path": f["file"], "line": f["line"], "body": comment_body(f)} for f in blocking + nits
    ]
    return {"body": body, "comments": comments}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    findings = json.loads((work / "classified.json").read_text())
    Path(sys.argv[2]).write_text(json.dumps(build_review(findings), indent=2))
    print(f"review with {len(findings)} findings written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
