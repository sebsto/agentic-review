#!/usr/bin/env python3
"""Stage 6: measure the agents against past review outcomes.

Usage: eval.py <claims|bugs|clean|all> <scratch dir> [case id ...]

Cases live in eval/cases.json:
  false-claim  A claim a maintainer proved wrong. The three verifiers must
               reject it. Measures how many false alarms the verifiers stop.
  bug          Defects a maintainer confirmed in one PR. The full pipeline must
               report each within `window` lines of the expected file and line,
               or anywhere in an `also_files` file for a cause that spans files.
               Measures recall, before and after the verifiers.
  clean        A PR merged with no review comments. The pipeline should report
               nothing. Every finding that survives is counted as a false alarm.

Each case is prepared at its recorded commit (`prepare.py --at`), with CI and
the later discussion left out. Nothing is ever posted. The summary is printed
and written to eval/results/<kind>.json.
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import ROOT
import find
from verify import VERIFIERS, decide, vote
from find import build_input

SCRIPTS = ROOT / "scripts"


def prepare(case: dict, scratch: Path) -> Path:
    work = scratch / case["id"]
    args = [sys.executable, str(SCRIPTS / "prepare.py"), case["pr"], str(work)]
    if case.get("sha"):
        args += ["--at", case["sha"]]
    done = subprocess.run(args, capture_output=True, text=True, check=False)
    if done.returncode:
        raise RuntimeError(f"prepare failed: {done.stderr.strip()[-300:]}")
    return work


def stage(name: str, work: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPTS / name), str(work)], capture_output=True, text=True, check=False
    )
    if done.returncode:
        raise RuntimeError(f"{name} failed: {done.stderr.strip()[-300:]}")


def run_claim(case: dict, scratch: Path) -> dict:
    """Ask the verifiers about one false claim. Pass means the quorum rejects it."""
    work = prepare(case, scratch)
    finding = {
        "id": "eval-1", "finder": "correctness", "file": case["file"], "line": case["line"],
        "title": case["claim"][:120], "explanation": case["claim"], "evidence": case["claim"],
    }
    context = build_input(work)
    votes = [vote(m, context, finding) for m in VERIFIERS]
    # A verifier that failed to answer is not a rejection; it must not make the case pass.
    valid = [v for v in votes if not v["reason"].startswith("verifier failed")]
    return {
        "id": case["id"],
        "pass": len(valid) >= 2 and not decide(valid),
        "votes": [v["real"] for v in valid],
        "failed_verifiers": len(votes) - len(valid),
        "in_prompt": case.get("in_prompt", False),
    }


def run_pipeline(case: dict, scratch: Path) -> dict:
    """Run finders, merge, verify and classify. Return findings before and after the vote."""
    work = prepare(case, scratch)
    failed = {n: r for n, r in find.run_finders(work).items() if isinstance(r, str)}
    for name in ("merge.py", "verify.py", "classify.py"):
        stage(name, work)
    found = json.loads((work / "findings.json").read_text())
    kept = json.loads((work / "classified.json").read_text())
    return {"found": found, "kept": kept, "failed_finders": failed}


def near(finding: dict, expect: dict) -> bool:
    if finding["file"] in expect.get("also_files", []):
        return True  # one root cause that shows in several files, any line counts
    return finding["file"] == expect["file"] and abs(finding["line"] - expect["line"]) <= expect["window"]


def hit(findings: list[dict], expect: dict) -> bool:
    return any(near(f, expect) for f in findings)


def run_case(case: dict, scratch: Path) -> dict:
    try:
        if case["kind"] == "false-claim":
            return run_claim(case, scratch)
        out = run_pipeline(case, scratch)
        brief = lambda items: [f"{f['file']}:{f['line']} {f['title'][:70]}" for f in items]
        if case["kind"] == "bug":
            expects = case["expect"]
            return {
                "id": case["id"],
                "pass": all(hit(out["kept"], e) for e in expects),
                "defects": len(expects),
                "found_by_finders": sum(hit(out["found"], e) for e in expects),
                "reported": sum(hit(out["kept"], e) for e in expects),
                "missed": [e["note"] for e in expects if not hit(out["kept"], e)],
                "kept": brief(out["kept"]),
                "failed_finders": list(out["failed_finders"]),
            }
        return {"id": case["id"], "pass": not out["kept"], "false_alarms": brief(out["kept"]), "failed_finders": list(out["failed_finders"])}
    except Exception as error:  # one broken case must not stop the eval
        return {"id": case["id"], "pass": False, "error": str(error)[:300]}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    wanted = {"claims": "false-claim", "bugs": "bug", "clean": "clean"}
    kinds = list(wanted.values()) if sys.argv[1] == "all" else [wanted[sys.argv[1]]]
    scratch = Path(sys.argv[2]).resolve()
    only = set(sys.argv[3:])
    cases = [
        c for c in json.loads((ROOT / "eval" / "cases.json").read_text())["cases"]
        if c["kind"] in kinds and (not only or c["id"] in only)
    ]
    with ThreadPoolExecutor(max_workers=1) as pool:
        results = list(pool.map(lambda c: run_case(c, scratch), cases))
    (ROOT / "eval" / "results").mkdir(exist_ok=True)
    for kind in kinds:
        mine = [r for r, c in zip(results, cases) if c["kind"] == kind]
        if not mine:
            continue
        passed = sum(1 for r in mine if r["pass"])
        label = {"false-claim": "false claims rejected", "bug": "bugs reported", "clean": "clean PRs with no finding"}[kind]
        print(f"{label}: {passed}/{len(mine)}")
        for r in mine:
            print(f"  {'ok  ' if r['pass'] else 'FAIL'} {r['id']} " + json.dumps({k: v for k, v in r.items() if k not in ('id', 'pass')}))
        (ROOT / "eval" / "results" / f"{kind}.json").write_text(json.dumps(mine, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
