"""Call a model through Amazon Bedrock with the AWS CLI. Standard library only.

The profile comes from the AGENTIC_REVIEW_AWS_PROFILE variable (default: "pro").
Every call has an explicit timeout so a hung request fails fast.
"""

import json
import os
import re
import tempfile
from pathlib import Path

from common import run

PROFILE = os.environ.get("AGENTIC_REVIEW_AWS_PROFILE", "pro")
REGION = os.environ.get("AGENTIC_REVIEW_AWS_REGION", "us-west-2")


def ask(model: str, system: str, user: str, max_tokens: int = 32000, timeout: int = 300) -> str:
    """Send one prompt to a Bedrock model and return the text of the answer."""
    request = {
        "modelId": model,
        "system": [{"text": system}],
        "messages": [{"role": "user", "content": [{"text": user}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    with tempfile.TemporaryDirectory() as tmp:
        request_file = Path(tmp) / "request.json"
        request_file.write_text(json.dumps(request))
        out = run(
            [
                "aws", "bedrock-runtime", "converse",
                "--profile", PROFILE, "--region", REGION,
                "--cli-read-timeout", str(timeout),
                "--cli-input-json", f"file://{request_file}",
            ],
            timeout=timeout + 30,
        )
    answer = json.loads(out)
    text = "".join(part.get("text", "") for part in answer["output"]["message"]["content"])
    if not text.strip():
        # Models that think first can spend the whole budget before answering.
        raise RuntimeError(f"empty answer from {model}, stopReason={answer['stopReason']}")
    return text


def extract_json(text: str):
    """Return the JSON value in a model answer, with or without a code fence."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return json.loads(fenced.group(1) if fenced else text)
