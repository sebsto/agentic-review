"""Run one thinking step as a Strands agent.

Every model call in the pipeline goes through `run_agent`. The agent may read
the PR checkout with three read-only tools, and it must answer with a typed
object. The scripts around it stay plain Python, so the order of the stages,
the checks and the post are never decided by a model.

Needs the `strands-agents` and `boto3` packages. The AWS profile and region
come from AGENTIC_REVIEW_AWS_PROFILE and AGENTIC_REVIEW_AWS_REGION. When the
profile is empty, boto3 uses its default credential chain (an IAM role on a server).
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Literal, TypeVar

import boto3
from botocore.config import Config
from pydantic import BaseModel, Field
from strands import Agent, tool
from strands.models import BedrockModel

PROFILE = os.environ.get("AGENTIC_REVIEW_AWS_PROFILE", "pro")
REGION = os.environ.get("AGENTIC_REVIEW_AWS_REGION", "us-west-2")
MAX_TOOL_CHARS = 20_000

TOOL_NOTE = (
    "\n\nYou can read the checked-out repository with read_file, grep and list_dir. "
    "Use them to look at callers, protocols, types and tests that the diff does not show. "
    "Make at most 15 tool calls. Return your answer by calling the structured output tool "
    "with the fields described above; that replaces any instruction to answer with JSON text."
)


class Finding(BaseModel):
    id: str
    finder: Literal["correctness", "modernity", "concurrency", "security", "cost-ux", "tests", "consistency"]
    file: str
    line: int = Field(ge=1)
    title: str = Field(max_length=120)
    explanation: str
    evidence: str
    suggested_fix: str | None = None


class Findings(BaseModel):
    """All findings for the pull request. Use an empty list when there are none."""

    findings: list[Finding]


class Verdict(BaseModel):
    finding_id: str
    real: bool
    reason: str


class Classified(BaseModel):
    finding_id: str
    # "class" is a Python keyword, so the field is aliased.
    kind: Literal["blocking", "nit", "pre-existing"] = Field(alias="class")
    reason: str


class ClassifiedList(BaseModel):
    """One item for each finding given."""

    items: list[Classified]


def repo_tools(repo: Path):
    """Return read-only tools confined to one checkout."""
    root = repo.resolve()

    def inside(path: str) -> Path:
        target = (root / path).resolve()
        if root != target and root not in target.parents:
            raise ValueError("path is outside the repository")
        return target

    @tool
    def read_file(path: str, start: int = 1, end: int = 400) -> str:
        """Read lines start..end (1-based) of a file in the repository. Path is relative to the repo root."""
        lines = inside(path).read_text(errors="ignore").splitlines()
        chunk = lines[max(start - 1, 0):end]
        return "\n".join(f"{start + i}: {row}" for i, row in enumerate(chunk))[:MAX_TOOL_CHARS]

    @tool
    def grep(pattern: str, path: str = ".") -> str:
        """Search Swift files for an extended regular expression. Returns file:line: text for up to 60 matches."""
        re.compile(pattern)  # fail early on a bad pattern
        done = subprocess.run(
            ["grep", "-rnE", "--include=*.swift", "-m", "20", "--", pattern, str(inside(path))],
            capture_output=True, text=True, timeout=30, check=False,
        )
        rows = [r.replace(str(root) + "/", "") for r in done.stdout.splitlines()[:60]]
        return "\n".join(rows)[:MAX_TOOL_CHARS] or "no matches"

    @tool
    def list_dir(path: str = ".") -> str:
        """List the entries of a directory in the repository."""
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in inside(path).iterdir())
        return "\n".join(entries)[:MAX_TOOL_CHARS]

    return [read_file, grep, list_dir]


T = TypeVar("T", bound=BaseModel)


def run_agent(model_id: str, system: str, prompt: str, output: type[T], repo: Path | None = None,
              timeout: int = 600) -> T:
    """Run one agent and return its answer as an `output` object.

    With `repo`, the agent gets the read-only repository tools. Raises when the
    model does not return a valid object.
    """
    session = boto3.Session(profile_name=PROFILE or None, region_name=REGION)
    model = BedrockModel(
        model_id=model_id, boto_session=session, max_tokens=32000,
        boto_client_config=Config(read_timeout=timeout, retries={"max_attempts": 2}),
    )
    agent = Agent(
        model=model,
        system_prompt=system + (TOOL_NOTE if repo else "\n\nReturn your answer by calling the structured output tool."),
        tools=repo_tools(repo) if repo else [],
        callback_handler=None,
    )
    result = agent(prompt, structured_output_model=output)
    if result.structured_output is None:
        raise RuntimeError(f"no structured answer from {model_id}")
    return result.structured_output
