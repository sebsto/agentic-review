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
import re
import sys
from pathlib import Path

from common import ROOT
from llm import ask, extract_json
from post import diff_lines
from validate import check, load_schema

DEFAULT_MODEL = "us.anthropic.claude-sonnet-5"
MAX_FILE_CHARS = 60_000


def files_missing_from_xcode_project(work: Path, files: list[str]) -> list[str]:
    """Return changed Swift files whose names no .pbxproj mentions.

    Projects that use folder-synchronised groups do not list files, so they are
    skipped. Only files the diff adds count; an old file may be listed under
    another path form.
    """
    repo = work / "repo"
    projects = [p.read_text(errors="ignore") for p in repo.glob("**/project.pbxproj") if ".build" not in p.parts]
    if not projects:
        return []
    # Folders that Xcode syncs by itself never list their files.
    synced = [
        path for text in projects
        for path in re.findall(r"PBXFileSystemSynchronizedRootGroup[^}]*?path = \"?([^;\"]+)\"?;", text)
    ]
    new_files = []
    current = ""
    previous_null = False
    for row in (work / "pr.diff").read_text().splitlines():
        if row.startswith("--- "):
            previous_null = row.startswith("--- /dev/null")
        elif row.startswith("+++ b/") and previous_null:
            current = row[6:]
            if current.endswith(".swift") and not current.startswith(("Tests/", ".build/")):
                new_files.append(current)
    return [
        f for f in new_files
        if not any(Path(f).name in text for text in projects)
        and not any(part in synced for part in Path(f).parts[:-1])
    ]


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
    unbuilt = files_missing_from_xcode_project(work, context["files"])
    if unbuilt:
        parts.append(
            "## Script check: Swift files in this PR that no Xcode project file mentions\n"
            "The repo has an Xcode project that lists its sources by name. These files are "
            "not in it, so an Xcode build will not compile them:\n"
            + "\n".join(f"- {name}" for name in unbuilt)
        )
    ci = work / "ci.txt"
    if ci.exists() and ci.read_text().strip():
        parts.append(f"## CI checks on this commit\n```\n{ci.read_text()[:3000]}\n```")
    discussion = work / "discussion.json"
    if discussion.exists() and json.loads(discussion.read_text()):
        parts.append(
            "## Earlier review discussion on this PR (do not repeat a point the author "
            "answered with a reason; respect decisions the maintainers made)\n"
            f"```json\n{discussion.read_text()[:20_000]}\n```"
        )
    build_log = work / "build.log"
    if build_log.exists():
        parts.append(f"## Build log\n```\n{build_log.read_text()[-20_000:]}\n```")
    review_md = work / "repo" / "REVIEW.md"
    if review_md.exists():
        parts.append(f"## Repo review rules (REVIEW.md)\n{review_md.read_text()}")
    return "\n\n".join(parts)


FINDERS = ["concurrency", "correctness", "modernity", "security", "cost-ux", "tests", "consistency"]


def run_finder(work: Path, name: str, model: str = DEFAULT_MODEL) -> tuple[int, int]:
    """Run one finder and write its files. Return (kept, rejected) counts."""
    system = (ROOT / "prompts" / "finder-common.md").read_text() + "\n\n" + (
        ROOT / "prompts" / f"finder-{name}.md"
    ).read_text()
    prompt = build_input(work)
    answer = None
    for _attempt in range(2):  # one retry: a call can time out or return malformed JSON
        try:
            answer = extract_json(ask(model, system, prompt, timeout=600))
            break
        except Exception as caught:
            error = caught
    if answer is None:
        raise RuntimeError(f"finder {name} failed twice: {error}")
    schema = load_schema("finding")
    visible = diff_lines((work / "pr.diff").read_text())

    kept, rejected = [], []
    for item in answer:
        item = {k: v for k, v in item.items() if v is not None}  # null means "not given"
        problems = check(item, schema)
        if not problems and (item["file"], item["line"]) not in visible:
            problems = ["line is not in the diff"]
        if problems:
            rejected.append({"finding": item, "problems": problems})
        else:
            kept.append(item)
    (work / f"findings-{name}.json").write_text(json.dumps(kept, indent=2))
    (work / f"findings-{name}.rejected.json").write_text(json.dumps(rejected, indent=2))
    return len(kept), len(rejected)


def run_finders(work: Path, names: list[str] = FINDERS) -> dict[str, tuple[int, int] | str]:
    """Run finders in parallel. A finder that fails is reported as an error string, not raised."""
    from concurrent.futures import ThreadPoolExecutor

    def one(name: str):
        try:
            return run_finder(work, name)
        except Exception as error:
            return str(error)[:300]

    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        return dict(zip(names, pool.map(one, names)))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    kept, rejected = run_finder(
        Path(sys.argv[1]), sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MODEL
    )
    print(f"{sys.argv[2]}: kept {kept}, rejected {rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
