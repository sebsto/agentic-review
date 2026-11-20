# agentic-review

A chain of AI agents that reviews a GitHub pull request for Swift 6 code.
It focuses on correctness, modern APIs, Swift 6 concurrency, security, and
user friendliness. For cloud projects it also checks cost.

Input: a GitHub PR URL. Output: one COMMENT review with a summary and inline
comments, each with a suggested fix.

## Pipeline

| Stage | Job | Runs as |
|---|---|---|
| 0. Prepare | Clone the PR in its own worktree. Run build, strict concurrency and lint. Keep the output. | script |
| 1. Find | Five finders in parallel: correctness, modernity, concurrency, security, cost/UX. Each returns JSON. | agents |
| 2. Merge | Remove duplicates. Drop style and cleanup items. | script |
| 3. Verify | Three verifiers per finding, on different models. A finding stays if 2 of 3 agree, with proof. | agents |
| 4. Classify | `blocking`, `nit` or `pre-existing` (checked with `git blame`). | agent |
| 5. Post | One COMMENT review: a summary that starts with a count, plus inline comments. | script |

Scripts own the clone, build, JSON checks and posting. Agents only reason.
Every agent output is checked against `schemas/`.

## Posting mode

Set per repo in `repos.json`:

- `auto`: the pipeline posts the review.
- `draft`: the pipeline stops after stage 5 and shows the review. A person approves before it is posted.

## Review rules

- Report only issues with proof: file, line, and a trace or output.
- Skip style, diagnostics and cleanup.
- Never repeat a finding already posted on the PR.
- After 3 rounds, re-review only the new diff and ask the author to rethink the approach.
- Flag the whole class of bug, not one line.
- A repo can add its own `REVIEW.md` to say what matters, what to skip and which paths to ignore.

## Eval

`eval/` holds past PRs with known bugs and clean PRs. Run the reviewer on both after each change.
Count missed bugs and false alarms.

## Status

Step 1 of 5: scaffold. Nothing runs yet.
