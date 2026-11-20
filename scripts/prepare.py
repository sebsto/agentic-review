#!/usr/bin/env python3
"""Stage 0: check out a PR and collect the facts the agents need.

Usage: prepare.py <PR URL> <work dir> [--build]

Writes into <work dir>:
  repo/          the PR head checked out
  pr.diff        the full PR diff
  context.json   repo, number, title, body, head/base SHAs, mode, changed files
  build.log      output of `swift build` with strict concurrency (only with --build)
"""

import json
import sys
from pathlib import Path

from common import mode_for, parse_pr_url, run


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    slug, number = parse_pr_url(sys.argv[1])
    work = Path(sys.argv[2]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    repo_dir = work / "repo"

    meta = json.loads(
        run(
            [
                "gh", "pr", "view", str(number), "-R", slug, "--json",
                "title,body,headRefOid,baseRefName,baseRefOid,files,state,isDraft",
            ]
        )
    )

    if not repo_dir.exists():
        run(["gh", "repo", "clone", slug, str(repo_dir), "--", "--filter=blob:none"])
    run(["git", "fetch", "-q", "origin", f"pull/{number}/head"], cwd=repo_dir)
    run(["git", "checkout", "-q", "--detach", meta["headRefOid"]], cwd=repo_dir)

    (work / "pr.diff").write_text(run(["gh", "pr", "diff", str(number), "-R", slug]))

    context = {
        "repo": slug,
        "number": number,
        "title": meta["title"],
        "body": meta["body"],
        "state": meta["state"],
        "head_sha": meta["headRefOid"],
        "base_ref": meta["baseRefName"],
        "base_sha": meta["baseRefOid"],
        "files": [f["path"] for f in meta["files"]],
        "mode": mode_for(slug),
    }
    (work / "context.json").write_text(json.dumps(context, indent=2))

    if "--build" in sys.argv and (repo_dir / "Package.swift").exists():
        # The build log is input for the finders. A failing build is a finding, not an error here.
        build = run_allow_fail(
            ["swift", "build", "-Xswiftc", "-strict-concurrency=complete"], repo_dir
        )
        (work / "build.log").write_text(build)

    print(f"prepared {slug}#{number} at {meta['headRefOid'][:9]} mode={context['mode']}")
    return 0


def run_allow_fail(args: list[str], cwd: Path) -> str:
    """Run a command and return stdout plus stderr whatever the exit code."""
    import subprocess

    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=1800, check=False
    )
    return f"exit={result.returncode}\n{result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    sys.exit(main())
