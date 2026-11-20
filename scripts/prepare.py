#!/usr/bin/env python3
"""Stage 0: check out a PR and collect the facts the agents need.

Usage: prepare.py <PR URL> <work dir> [--build] [--at <sha>]

Writes into <work dir>:
  repo/          the PR head checked out
  pr.diff        the full PR diff
  context.json   repo, number, title, body, head/base SHAs, mode, changed files
  build.log      output of `swift build` with strict concurrency (only with --build)
"""

import json
import subprocess
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
    at = sys.argv[sys.argv.index("--at") + 1] if "--at" in sys.argv else None
    if at:
        # Eval mode: look at the PR as it was at an earlier commit. The diff is
        # taken against the fork point, and CI and the later discussion are
        # left out, because they would reveal the answer.
        if subprocess.run(["git", "cat-file", "-e", at], cwd=repo_dir, check=False).returncode:
            run(["git", "fetch", "-q", "origin", at], cwd=repo_dir)
        run(["git", "fetch", "-q", "origin", meta["baseRefName"]], cwd=repo_dir)
        run(["git", "checkout", "-q", "--detach", at], cwd=repo_dir)
        head = run(["git", "rev-parse", "HEAD"], cwd=repo_dir).strip()
        fork = run(["git", "merge-base", head, f"origin/{meta['baseRefName']}"], cwd=repo_dir).strip()
        if fork == head:
            # The commit is already on the base branch (a merged PR). Start from
            # the parent of the PR's first commit instead.
            first = json.loads(
                run(["gh", "pr", "view", str(number), "-R", slug, "--json", "commits"])
            )["commits"][0]["oid"]
            fork = run(["git", "rev-parse", f"{first}^"], cwd=repo_dir).strip()
        (work / "pr.diff").write_text(run(["git", "diff", f"{fork}..{head}"], cwd=repo_dir))
        meta["headRefOid"] = head
        meta["baseRefOid"] = fork
        meta["files"] = [
            {"path": p} for p in run(["git", "diff", "--name-only", f"{fork}..{head}"], cwd=repo_dir).split()
        ]
    else:
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

    # CI result and earlier review discussion. Verifiers use them as evidence:
    # a claim "this does not compile" is wrong if CI built this commit, and a
    # point the author already answered with a reason must not be repeated.
    threads = [] if at else json.loads(
        run(["gh", "api", f"repos/{slug}/pulls/{number}/comments?per_page=100"])
    )
    if not at:
        (work / "ci.txt").write_text(
            run_allow_fail(["gh", "pr", "checks", str(number), "-R", slug], work)
        )
    discussion = [
        {"id": c["id"], "reply_to": c.get("in_reply_to_id"), "author": c["user"]["login"],
         "path": c["path"], "body": c["body"][:1500]}
        for c in threads
    ]
    (work / "discussion.json").write_text(json.dumps(discussion, indent=2))

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
