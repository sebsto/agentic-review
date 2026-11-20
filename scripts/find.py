#!/usr/bin/env python3
"""Stage 1: run one finder over a prepared PR.

Usage: find.py <work dir> <finder name> [model]

Reads prompts/finder-<name>.md, the PR diff, the full text of each changed
Swift file, the build log and the repo's REVIEW.md if present. Writes
<work dir>/findings-<name>.json, a list checked against schemas/finding.schema.json.
Findings that fail the check, or point at a line outside the diff, are dropped
and counted.
"""

import json
import sys
from pathlib import Path

from common import ROOT
from llm import ask, extract_json
from post import diff_lines
from validate import check, load_schema

DEFAULT_MODEL = "us.anthropic.claude-sonnet-5"
MAX_FILE_CHARS = 60_000


def build_input(work: Path) -> str:
    """Assemble everything the finder may look at into one prompt."""
    context = json.loads((work / "context.json").read_text())
    parts = [
        f"Pull request {context['repo']}#{context['number']}: {context['title']}\n\n{context['body']}",
        f"## Diff\n```diff\n{(work / 'pr.diff').read_text()}\n```",
    ]
    for path in context["files"]:
        file = work / "repo" / path
        if path.endswith(".swift") and file.is_file():
            parts.append(f"## Full file: {path}\n```swift\n{file.read_text()[:MAX_FILE_CHARS]}\n```")
    build_log = work / "build.log"
    if build_log.exists():
        parts.append(f"## Build log\n```\n{build_log.read_text()[-20_000:]}\n```")
    review_md = work / "repo" / "REVIEW.md"
    if review_md.exists():
        parts.append(f"## Repo review rules (REVIEW.md)\n{review_md.read_text()}")
    return "\n\n".join(parts)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    name = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL

    system = (ROOT / "prompts" / f"finder-{name}.md").read_text()
    answer = extract_json(ask(model, system, build_input(work)))
    schema = load_schema("finding")
    visible = diff_lines((work / "pr.diff").read_text())

    kept, rejected = [], []
    for item in answer:
        problems = check(item, schema)
        if not problems and (item["file"], item["line"]) not in visible:
            problems = ["line is not in the diff"]
        if problems:
            rejected.append({"finding": item, "problems": problems})
        else:
            kept.append(item)
    (work / f"findings-{name}.json").write_text(json.dumps(kept, indent=2))
    (work / f"findings-{name}.rejected.json").write_text(json.dumps(rejected, indent=2))
    print(f"{name}: kept {len(kept)}, rejected {len(rejected)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
