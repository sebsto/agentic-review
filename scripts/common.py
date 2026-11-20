"""Shared helpers for the agentic-review scripts. Standard library only."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PR_URL = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")


def parse_pr_url(url: str) -> tuple[str, int]:
    """Return ("owner/name", number) for a GitHub PR URL, or raise ValueError."""
    match = PR_URL.match(url.strip())
    if not match:
        raise ValueError(f"not a GitHub PR URL: {url}")
    return f"{match.group(1)}/{match.group(2)}", int(match.group(3))


def mode_for(slug: str) -> str:
    """Return the posting mode ("auto" or "draft") configured for a repo."""
    config = json.loads((ROOT / "repos.json").read_text())
    entry = config["repos"].get(slug, config["default"])
    mode = entry["mode"]
    if mode not in ("auto", "draft"):
        raise ValueError(f"bad mode {mode!r} for {slug}")
    return mode


def run(args: list[str], cwd: Path | None = None, timeout: int = 600) -> str:
    """Run a command without a shell and return its stdout. Raise on failure."""
    result = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout
