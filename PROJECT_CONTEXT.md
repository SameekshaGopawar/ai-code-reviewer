# Project Overview

## Goal
An AI-assisted code reviewer: run standard Python static analyzers (pylint, flake8,
bandit), normalize their output into a common schema, then feed the source code +
findings to an LLM (OpenAI `gpt-4o`) to produce a structured, human-readable code
review with severities and per-line comments. Exposed as a CLI.

## Current architecture
```
CLI (cli.py)
  ├─ default mode: run static analyzers only, print/write findings JSON
  └─ --review mode:
        analyzers.analyze(target)  →  list[Finding] (normalized dict)
        llm_reviewer.review_file(target)
            ├─ reads source file text
            ├─ calls analyze(target) again for findings
            ├─ builds a user message: findings JSON + fenced source code
            ├─ calls OpenAI chat.completions.create() with a strict
            │   JSON-schema response_format (REVIEW_SCHEMA)
            └─ returns parsed {"summary": ..., "comments": [...]}
        CLI prints summary + comments sorted by severity (critical → warning → suggestion)
```

Static analyzers are invoked as subprocesses (`python -m pylint/flake8/bandit`) and
their tool-specific output (JSON for pylint/bandit, line-based text for flake8) is
parsed into a single `Finding` dataclass shape. `analyze()` merges and sorts findings
from all three tools by (file, line) before returning them as plain dicts.

## Folder structure
```
ai-code-reviewer/
├── ai_code_reviewer/
│   ├── __init__.py
│   ├── analyzers.py      # pylint/flake8/bandit wrappers → normalized Finding list
│   ├── cli.py            # argparse entrypoint, two modes (analyze-only / --review)
│   └── llm_reviewer.py   # builds prompt, calls OpenAI, returns structured review
├── sample_code/
│   ├── example.py                    # intentionally-flawed sample (unused import,
│   │                                  # shell=True command injection, style issues)
│   ├── logistic_regression.py        # pure-Python (no deps) logistic regression demo,
│   │                                  # has a mutable-default-arg bug + shadowing issues
│   └── iris_logistic_regression.py   # sklearn logistic regression on Iris; currently
│                                      # has an INTENTIONAL bug (train_test_split return
│                                      # values unpacked in the wrong order — swapped
│                                      # X_test/y_train) + an unused numpy import, added
│                                      # on purpose to demo the reviewer catching bugs
├── tests/
│   ├── __init__.py
│   ├── test_analyzers.py   # unit tests for pylint/flake8/bandit parsing + analyze()
│   ├── test_llm_reviewer.py # unit tests for review_file() using an injected mock
│   │                         # OpenAI client (no real API calls/key needed)
│   └── test_cli.py          # subprocess smoke tests for the CLI's analyze-only mode
├── demo.ipynb              # Jupyter notebook walking through the pipeline step-by-step
│                            # (read file -> analyze() -> review_file() -> pretty print);
│                            # TARGET variable in the first cell picks which file to review
├── scripts/
│   └── post_pr_review.py   # reviews changed .py files in a PR diff, posts one
│                           # combined comment via `gh pr comment`
├── .github/
│   ├── workflows/
│   │   ├── ci.yml          # runs lint (informational) + pytest w/ coverage on
│   │   │                   # push/PR to main or master
│   │   └── ai-review.yml   # on pull_request: checks out full history, calls the
│   │                       # local composite action below to post an AI review
│   │                       # comment on the PR
│   └── actions/
│       └── ai-code-review/
│           └── action.yml  # composite action: sets up Python, installs deps,
│                            # runs scripts/post_pr_review.py with the PR's
│                            # base ref + number and the OPENAI_API_KEY /
│                            # GITHUB_TOKEN secrets wired in as env vars
├── requirements.txt        # pylint, flake8, bandit, openai, python-dotenv, pytest,
│                            # pytest-cov
├── .env / .env.example    # OPENAI_API_KEY (real .env is gitignored)
├── .gitignore
└── venv/                  # local virtualenv (gitignored)
```

## Major files and responsibilities
- **`ai_code_reviewer/analyzers.py`** — `Finding` dataclass; `run_pylint`, `run_flake8`,
  `run_bandit` each shell out to the tool and map its native severity vocabulary onto
  `"suggestion" | "warning" | "critical"`; `analyze(target)` is the public entrypoint
  that runs all three and returns a sorted flat list of dicts.
- **`ai_code_reviewer/llm_reviewer.py`** — owns the LLM side: `SYSTEM_PROMPT` (review
  instructions/tone), `REVIEW_SCHEMA` (JSON schema enforced via OpenAI's strict
  structured-output mode), `_build_user_message` (findings + source code), and
  `review_file(target, client=None)` which ties analyzers + OpenAI call together and
  returns the parsed review dict. Accepts an injected `client` for testability.
- **`ai_code_reviewer/cli.py`** — argparse CLI with `target`, `-o/--output`, and
  `--review` flags. Without `--review`, prints/writes raw findings JSON. With
  `--review`, runs the full LLM pipeline and pretty-prints (or writes JSON of) the
  result via `_print_review`, sorted by severity.

# Completed Work

## Everything implemented so far
- Static analysis wrappers for pylint, flake8, and bandit with output normalization
  into a shared `Finding` schema.
- LLM review pipeline using OpenAI's `gpt-4o` with strict JSON-schema structured
  output (`response_format: json_schema`, `strict: True`).
- CLI with two modes: raw findings JSON, or full LLM-backed review.
- `sample_code/example.py`: a deliberately flawed file (unused `os` import, a
  `subprocess.call(..., shell=True)` command-injection risk, missing docstrings,
  non-PascalCase class name) used to exercise the full pipeline end-to-end.

## What was tested (2026-07-25)
Ran the full pipeline end-to-end using a real OpenAI API key configured in `.env`:
```
python -m ai_code_reviewer.cli sample_code/example.py --review
python -m ai_code_reviewer.cli sample_code/example.py            # analyzers only
```
Verified:
1. All three static analyzers (pylint, flake8, bandit) execute successfully as
   subprocesses and return parseable output.
2. Findings normalize correctly into the common `Finding` schema (tool, file, line,
   column, code, message, severity) and sort by (file, line).
3. The LLM receives both the raw source code (fenced) and the full findings JSON in
   the user message, per `_build_user_message`.
4. The OpenAI structured-output JSON (matching `REVIEW_SCHEMA`) parses cleanly with
   `json.loads(response.choices[0].message.content)` — no schema violations.
5. The CLI prints a correct final review: a 1-3 sentence summary plus per-comment
   severity/line/title/body, sorted critical → warning → suggestion.

## Test results
Full run against `sample_code/example.py --review` succeeded on the first attempt —
no code changes were required. Output included:
- 1 CRITICAL (line 11): command injection risk from `subprocess.call(..., shell=True)`
  with unsanitized user input.
- 1 WARNING (line 2): general subprocess/shell risk.
- 5 SUGGESTIONs: unused `os` import, missing docstrings (module/functions/class),
  non-PascalCase class name `calculator`.

Raw analyzer-only run (no `--review`) independently confirmed: bandit found B404
(line 2) and B602 (line 11, critical); flake8 found F401 (line 1, unused import,
mapped to critical per the `F`-prefix rule in `analyzers.py`); pylint found 7
findings (missing docstrings, unused import, naming, too-few-public-methods).

## Bugs fixed during testing
None. The pipeline ran correctly end-to-end on the first execution — analyzers,
normalization, OpenAI call with structured output, and CLI printing all worked
without modification.

## Automated test suite (added 2026-07-26)
Added `tests/test_analyzers.py`, `tests/test_llm_reviewer.py`, and `tests/test_cli.py`
using pytest (added to `requirements.txt`). All 15 tests pass.
- `test_analyzers.py`: mocks `ai_code_reviewer.analyzers._run` (the subprocess wrapper)
  to feed canned pylint/flake8/bandit output and asserts correct `Finding` parsing +
  severity mapping per tool, plus `analyze()`'s sort-by-(file,line) behavior and its
  `FileNotFoundError` on a missing target.
- `test_llm_reviewer.py`: uses a `unittest.mock.MagicMock` standing in for the `OpenAI`
  client (passed via `review_file(target, client=...)`, which the function already
  supported) so no real API key or network call is needed. Verifies the parsed review
  dict is returned correctly and that the source code + findings actually end up in the
  message sent to the model.
- `test_cli.py`: subprocess-based smoke tests that actually invoke
  `python -m ai_code_reviewer.cli <target>` (analyze-only mode, no `--review`, so no
  API key needed) and check the printed JSON is a well-formed findings list; also
  checks a missing-file target exits non-zero.

Run with: `python -m pytest tests/ -v` (from the project root, venv activated).

`test_cli.py` includes both **in-process** tests (call `main()` directly with
monkeypatched `sys.argv`/`capsys`, needed for `pytest-cov` to see coverage inside
`cli.py` — subprocess-based tests run in a separate process pytest-cov can't see
into) and the original **subprocess** smoke tests (true black-box, closer to how a
real user invokes the CLI). Both styles are kept intentionally.

## Test coverage (added 2026-07-26)
Added `pytest-cov` to `requirements.txt`. Current coverage, run via:
```
python -m pytest tests/ --cov=ai_code_reviewer --cov-report=term-missing
```
Result: **97% overall** (118 statements, 3 missed) — 19 tests, all passing.
- `analyzers.py`: 97% (lines 99-100 uncovered — an edge case in `run_bandit`)
- `cli.py`: 97% (line 47 uncovered — the `if __name__ == "__main__":` guard, not
  meaningfully testable/necessary to cover)
- `llm_reviewer.py`: 100%

(Coverage command only measures `ai_code_reviewer/`; `scripts/post_pr_review.py`
has its own tests in `tests/test_post_pr_review.py` covering the pure formatting
logic and the git-diff file-filtering logic, 22 tests total across the whole suite.)

## CI + PR automation (added 2026-07-26)
Two GitHub Actions workflows were added under `.github/workflows/`:

1. **`ci.yml`** — runs on every push to `main`/`master` and on every PR. Installs
   deps, runs pylint/flake8/bandit as informational-only (`--exit-zero`, so style
   nits don't fail the build — see "Important Design Decisions" below for why),
   then runs `pytest tests/ -v --cov=ai_code_reviewer --cov-report=term-missing`.
   This job is what should actually gate merges (it fails if tests fail).

2. **`ai-review.yml`** — runs on `pull_request` (opened/synchronize/reopened).
   Checks out full git history (`fetch-depth: 0`, needed to diff against the base
   branch) and calls a local composite action, `.github/actions/ai-code-review/`,
   which:
   - Installs `requirements.txt`
   - Runs `scripts/post_pr_review.py` with `OPENAI_API_KEY` (from a repo secret)
     and `GH_TOKEN` (from the workflow's automatic `secrets.GITHUB_TOKEN`) as
     env vars, along with the PR's base ref and number from the GitHub Actions
     event context (`github.event.pull_request.*`)

`scripts/post_pr_review.py` itself:
- Runs `git fetch origin <base_ref>` then `git diff --name-only --diff-filter=d
  origin/<base_ref>...HEAD -- '*.py'` to get the list of changed (non-deleted)
  Python files in the PR
- Calls `review_file()` (the same function the CLI uses) on each changed file
- Formats all results into one Markdown comment (severity emoji + sorted
  critical → warning → suggestion, grouped per file under a `### \`path\`` heading)
- Posts it as a single PR comment via `gh pr comment <number> --body-file ...`
  (the `gh` CLI ships preinstalled on GitHub-hosted runners and auto-authenticates
  via `GH_TOKEN`)

**Verified live on GitHub (2026-07-26):** repo pushed to
`github.com/SameekshaGopawar/ai-code-reviewer` (private), `OPENAI_API_KEY` secret
added, and a real test PR (#1, since merged + branch deleted) confirmed both
`ci.yml` and `ai-review.yml` run green — `ai-review.yml` posted a genuine
GPT-4o-generated review comment on the PR reviewing `sample_code/logistic_regression.py`,
catching the mutable-default-argument bug, variable shadowing, and missing
docstrings, exactly as designed. The whole pipeline is confirmed working
end-to-end on GitHub, not just locally.

## Additional sample files (added 2026-07-26)
Two more files were added under `sample_code/` to make manual testing more relatable
for ML-focused review scenarios (in addition to `example.py`):
- `logistic_regression.py` — pure standard-library (no numpy/sklearn) logistic
  regression, intentionally includes a mutable-default-argument bug (`weights=[]`)
  and several variable-shadowing issues.
- `iris_logistic_regression.py` — uses real `scikit-learn` (now in `requirements.txt`
  and installed in the venv) on the Iris dataset. Currently contains an **intentional**
  bug for demo purposes: `X_train, y_train, X_test, y_test = train_test_split(...)` —
  the middle two names are swapped (should be `X_train, X_test, y_train, y_test`),
  which would break `model.fit(X_train, y_train)` at runtime. Also has an unused
  `import numpy as np`. The `--review` pipeline correctly flags both issues. If you
  want a "clean" reference version to compare against, the correct unpacking order is
  `X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)`.

A Jupyter notebook, `demo.ipynb`, was also added at the repo root — it runs the same
pipeline as the CLI's `--review` mode but as separate cells (read file -> analyze() ->
review_file() -> pretty-print) so each stage's output is visible inline. Change the
`TARGET` variable in its first code cell to point at a different file, then re-run.
Requires selecting the project's own venv as the Jupyter kernel in VS Code (kernel name:
"Python (ai-code-reviewer venv)" / "ai-code-reviewer-venv").

# Current Status

## What is working
- Static analysis (pylint/flake8/bandit) → normalized findings: working.
- LLM review pipeline (OpenAI gpt-4o, structured JSON output): working, verified
  with a real API call, on multiple sample files (a generic flawed file, a pure-Python
  ML file, and a scikit-learn ML file).
- CLI (`analyze` mode and `--review` mode, plus `-o/--output` file writing): working.
- `.env`-based config via `python-dotenv`; `.env` is gitignored, `.env.example`
  documents the required `OPENAI_API_KEY` var.
- Automated test suite: 15 pytest tests across `test_analyzers.py`,
  `test_llm_reviewer.py`, and `test_cli.py` — all passing. `llm_reviewer` tests use a
  mocked OpenAI client, no API key required to run the suite.
- `demo.ipynb` Jupyter notebook: an alternative, step-by-step way to run the same
  pipeline with visible intermediate output per stage.

## What is not implemented yet
- No support for reviewing multiple files/directories in `--review` mode (the LLM
  review path is explicitly single-file only; `analyze()` itself does support a
  directory target since it just passes `target` through to each tool).
- No caching/rate-limit handling around the OpenAI call.
- No dashboard or any UI beyond the CLI (intentionally deprioritized — see
  "Remaining roadmap" below).
- CI (`ci.yml`) and PR automation (`ai-review.yml`) workflows are written and
  locally validated (YAML syntax + unit tests on the pure logic), **but not yet
  pushed to GitHub or run for real** — the repo has no GitHub remote yet. This is
  the actual next step, see "Immediate next task."

# Next Steps

## Immediate next task
The project is complete and verified end-to-end (pipeline, 22-test suite at 97%
coverage, git history, CI, and PR automation all confirmed working live on
GitHub — see "CI + PR automation" above). There is no blocking next task.
If resuming work, the "nice-to-haves" in the roadmap below are the logical
next targets, but none of them are required for the project to be considered done.

## Remaining roadmap
1. ~~Automated tests~~ — done (22 passing pytest tests, 97% coverage).
2. ~~Initial git commit~~ — done.
3. ~~GitHub Actions CI~~ — done and verified live (`.github/workflows/ci.yml`).
4. ~~PR automation~~ — done and verified live (`.github/workflows/ai-review.yml` +
   `.github/actions/ai-code-review/action.yml` + `scripts/post_pr_review.py`),
   confirmed posting real AI review comments on an actual GitHub PR.
5. **Optional dashboard** — intentionally skipped/deprioritized (a CLI + working
   GitHub Action already tells a stronger portfolio story than a hosted dashboard
   for this kind of tool — see conversation history for the reasoning).
6. Nice-to-haves if picked back up later: support directory/multi-file targets in
   `--review` mode (currently single-file only), make the `MODEL` constant in
   `llm_reviewer.py` configurable, add rate-limit/retry handling around the OpenAI
   call.

## Repo location
Pushed to `github.com/SameekshaGopawar/ai-code-reviewer` (private). Local remote
`origin` already points there; `master` is the only branch (test branch used for
GitHub Actions verification was merged and deleted).

# Important Design Decisions

## Prompt format
- `SYSTEM_PROMPT` (in `llm_reviewer.py`) instructs the model to act as an
  experienced reviewer, to *not* parrot static-analysis findings verbatim, to
  group related issues, explain *why* they matter, skip minor style nits, add its
  own findings the tools missed, tie every comment to a line number, and assign a
  severity from a fixed 3-level enum.
- The user message (`_build_user_message`) is: static analysis findings as JSON,
  followed by the full source file in a fenced ```python block. Both are sent
  together in a single OpenAI chat call — no multi-turn/agentic loop, no
  chunking of large files.

## Finding schema
Every static-analysis finding is normalized to:
```python
Finding(tool: str, file: str, line: int, column: int, code: str, message: str,
        severity: "suggestion" | "warning" | "critical")
```
Severity mapping per tool:
- **pylint**: convention/refactor → suggestion, warning → warning, error/fatal → critical.
- **flake8**: E/W/C-prefixed codes → warning; F-prefixed (pyflakes, real bugs like
  unused imports/undefined names) → critical.
- **bandit**: LOW → suggestion, MEDIUM → warning, HIGH → critical.

`analyze()` concatenates all three tools' findings and sorts by `(file, line)`.

## LLM response schema
Enforced via OpenAI structured outputs (`response_format.type = "json_schema"`,
`strict: True`) so the model cannot deviate from the shape:
```json
{
  "summary": "1-3 sentence overall assessment",
  "comments": [
    {"line": int, "severity": "critical|warning|suggestion",
     "title": "short title", "comment": "explanation and suggested fix"}
  ]
}
```
`additionalProperties: False` is set on both the top-level object and each comment
object, so the schema is strict end-to-end.

## Assumptions / implementation details
- `--review` mode is single-file only (`review_file` calls `path.read_text()` on
  exactly one file); passing a directory will fail. Analyze-only mode (`analyze()`)
  can take a directory since it forwards `target` straight to each tool's CLI.
- `MODEL = "gpt-4o"` is hardcoded in `llm_reviewer.py`, not configurable via env/CLI
  flag yet.
- `analyze()` is called twice per `--review` invocation (once inside `review_file`,
  and the CLI doesn't call it separately in that path) — not a bug, just worth
  knowing if optimizing for speed later.
- Analyzer subprocesses are invoked as `python -m <tool>` using `sys.executable`,
  so they always run under the same interpreter/venv as the CLI itself.
- OpenAI API key is loaded via `python-dotenv` (`load_dotenv()` at import time in
  `llm_reviewer.py`) from a `.env` file at the repo root; `.env` is gitignored,
  `.env.example` shows the expected `OPENAI_API_KEY` var name.
- No commits exist in this repo yet — all current files are untracked in git.
