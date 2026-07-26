# AI Code Reviewer

A code review tool that combines traditional static analysis with an LLM.
It runs pylint, flake8, and bandit against a Python file, normalizes their
output into a common schema, then feeds the source code and those findings
to OpenAI's GPT-4o to produce a structured, severity-ranked code review —
available as a CLI and as an automated GitHub Action that comments on pull
requests.

## Why

Static analyzers are fast and reliable but noisy — they report every style
nit with the same weight as a real bug, and they can't explain *why*
something matters or catch issues outside their fixed rule set. An LLM,
given both the code and the analyzers' findings, can group related issues,
filter out the noise, add its own observations (like a command-injection
risk none of the three tools caught), and write the kind of review a human
reviewer would actually leave.

## How it works

```
source file ──┬──> pylint  ──┐
              ├──> flake8  ──┼──> normalized findings ──┐
              └──> bandit  ──┘                          │
                                                          ▼
                                              OpenAI GPT-4o (structured
                                              JSON output, strict schema)
                                                          │
                                                          ▼
                                          summary + severity-ranked comments
```

## Features

- **Static analysis**: pylint, flake8, and bandit results merged into one
  finding schema (`tool`, `file`, `line`, `column`, `code`, `message`,
  `severity`)
- **LLM review**: source code + findings sent to GPT-4o with a strict JSON
  schema response, so the output is always well-formed — a summary plus a
  list of comments, each with a line number, severity
  (`critical`/`warning`/`suggestion`), title, and explanation
- **CLI**: analyze-only mode (just the raw findings) or `--review` mode
  (full LLM-backed review), with optional JSON file output
- **GitHub Action**: automatically reviews changed Python files on every
  pull request and posts one combined comment
- **Interactive notebook**: `demo.ipynb` runs the same pipeline step-by-step
  with visible output at each stage

## Setup

```bash
git clone <this-repo>
cd ai-code-reviewer
python -m venv venv
source venv/Scripts/activate   # Windows; use venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then add your OPENAI_API_KEY
```

## Usage

Static analysis only, printed as JSON:
```bash
python -m ai_code_reviewer.cli path/to/file.py
```

Full AI-backed review:
```bash
python -m ai_code_reviewer.cli path/to/file.py --review
```

Write output to a file instead of stdout:
```bash
python -m ai_code_reviewer.cli path/to/file.py --review -o review.json
```

Or run `demo.ipynb` in Jupyter/VS Code to see each pipeline stage's output
inline — change the `TARGET` variable in the first cell to point at a
different file.

## GitHub Action (automated PR review)

`.github/workflows/ai-review.yml` reviews every pull request automatically:
on each PR, it diffs against the base branch, runs the review pipeline on
every changed `.py` file, and posts one combined comment with all findings.
Requires an `OPENAI_API_KEY` repository secret (Settings → Secrets and
variables → Actions).

`.github/workflows/ci.yml` runs the lint tools (informational) and the full
test suite with coverage on every push and pull request.

## Testing

```bash
python -m pytest tests/ -v --cov=ai_code_reviewer --cov-report=term-missing
```
22 tests, 97% coverage. LLM-dependent tests use a mocked OpenAI client, so
the suite runs without an API key or network access.

## Tech stack

Python 3.11 · OpenAI API (GPT-4o, structured outputs) · pylint · flake8 ·
bandit · pytest / pytest-cov · GitHub Actions

## Project structure

```
ai_code_reviewer/
├── analyzers.py      # pylint/flake8/bandit wrappers -> normalized findings
├── cli.py            # CLI entrypoint
└── llm_reviewer.py   # prompt construction + OpenAI call

scripts/post_pr_review.py     # posts the AI review as a PR comment
.github/workflows/            # CI + automated PR review
.github/actions/ai-code-review/  # reusable composite action
tests/                         # pytest suite
sample_code/                   # example files used for manual/demo testing
demo.ipynb                     # interactive step-by-step walkthrough
```

See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for detailed architecture notes,
design decisions, and development history.
