#!/usr/bin/env python3
"""Run all stages on one PR.

Usage: run.py <PR URL> <work dir> [--build] [--approve]

Stage 0 prepare, 1 five finders in parallel, 2 merge, 3 verify, 4 classify,
5 report and post. Posting follows the repo's mode in repos.json: "auto" posts,
"draft" prints the review and waits for --approve.
"""

import subprocess
import sys
from pathlib import Path

import find
from common import ROOT

SCRIPTS = ROOT / "scripts"


def script(name: str, *args: str) -> None:
    """Run one stage script and show its output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, check=False
    )
    print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stdout + result.stderr)
        raise SystemExit(f"{name} failed")


def all_failed(results: dict) -> bool:
    """True when every finder returned an error string, so "0 findings" would be meaningless."""
    return bool(results) and all(isinstance(r, str) for r in results.values())


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    url = sys.argv[1]
    work = Path(sys.argv[2]).resolve()
    flags = [a for a in sys.argv[3:] if a in ("--build", "--approve")]
    script("prepare.py", url, str(work), *[f for f in flags if f == "--build"])
    results = find.run_finders(work)
    for name, result in results.items():
        print(f"{name}: {result}" if isinstance(result, str) else f"{name}: kept {result[0]}, rejected {result[1]}")
    if all_failed(results):
        raise SystemExit("every finder failed; refusing to report this PR as clean")
    script("merge.py", str(work))
    script("verify.py", str(work))
    script("classify.py", str(work))
    script("report.py", str(work), str(work / "review.json"))
    script("post.py", str(work), str(work / "review.json"), *[f for f in flags if f == "--approve"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
