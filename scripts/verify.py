#!/usr/bin/env python3
"""Stage 3: verify each merged finding with three verifiers on different models.

Usage: verify.py <work dir>

Reads <work dir>/findings.json. Each finding goes to every verifier model. A
finding stays when at least QUORUM verifiers say it is real; a verifier that
fails or answers badly counts as "not real". Writes <work dir>/verified.json
(kept findings, each with its votes) and <work dir>/verdicts.json (all votes).
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import ROOT
from find import build_input
from agent import Verdict, run_agent

VERIFIERS = [
    "us.anthropic.claude-opus-5",
    "us.anthropic.claude-sonnet-5",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
]
QUORUM = 2


def vote(model: str, context: str, finding: dict, repo: Path | None = None) -> dict:
    """Ask one verifier about one finding. Always return a valid verdict."""
    system = (ROOT / "prompts" / "verifier.md").read_text()
    user = f"{context}\n\n## Claimed defect\n```json\n{json.dumps(finding, indent=2)}\n```"
    error: Exception | None = None
    for _attempt in range(2):  # one retry: a call can time out or return an invalid answer
        try:
            verdict = run_agent(model, system, user, Verdict, repo=repo).model_dump()
            verdict["finding_id"] = finding["id"]
            return {"model": model, **verdict}
        except Exception as caught:  # a failed vote must not stop the run
            error = caught
    return {"model": model, "finding_id": finding["id"], "real": False,
            "reason": f"verifier failed: {error}"}


def decide(votes: list[dict]) -> bool:
    return sum(1 for v in votes if v["real"]) >= QUORUM


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    work = Path(sys.argv[1])
    findings = json.loads((work / "findings.json").read_text())
    context = build_input(work)
    jobs = [(m, f) for f in findings for m in VERIFIERS]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda job: vote(job[0], context, job[1], work / "repo"), jobs))
    verdicts = {f["id"]: [r for r in results if r["finding_id"] == f["id"]] for f in findings}
    kept = [{**f, "votes": verdicts[f["id"]]} for f in findings if decide(verdicts[f["id"]])]
    (work / "verdicts.json").write_text(json.dumps(verdicts, indent=2))
    (work / "verified.json").write_text(json.dumps(kept, indent=2))
    print(f"verified {len(kept)} of {len(findings)} findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
