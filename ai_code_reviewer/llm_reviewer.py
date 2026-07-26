"""Feeds source code plus static-analysis findings into an LLM and gets back
human-readable review comments with severity levels."""
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from ai_code_reviewer.analyzers import analyze

load_dotenv()

MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are an experienced code reviewer. You are given a source file \
and a list of findings from static analysis tools (pylint, flake8, bandit).

Write a code review that a human would actually find useful:
- Don't just restate each static-analysis finding verbatim. Group related ones, \
explain *why* something matters, and skip pure style nits that don't affect \
correctness, security, or readability unless they're egregious.
- Add your own findings if you notice bugs, security issues, or bad practices \
that the static analysis tools missed.
- Every comment must reference a specific line number in the file.
- Assign each comment a severity: "critical" (bugs, security issues), \
"warning" (bad practice, likely-latent bug), or "suggestion" (style, clarity, \
minor optimization).
- Write a short overall summary of the file's quality.
"""

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "1-3 sentence overall assessment"},
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["critical", "warning", "suggestion"]},
                    "title": {"type": "string", "description": "short title, e.g. 'Command injection risk'"},
                    "comment": {"type": "string", "description": "explanation and suggested fix"},
                },
                "required": ["line", "severity", "title", "comment"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "comments"],
    "additionalProperties": False,
}


def _build_user_message(code: str, findings: list[dict]) -> str:
    findings_text = json.dumps(findings, indent=2) if findings else "(none)"
    return (
        f"Static analysis findings:\n{findings_text}\n\n"
        f"Source file:\n```python\n{code}\n```"
    )


def review_file(target: str, client: OpenAI | None = None) -> dict:
    """Run static analysis + LLM review on a single Python file.
    Returns {"summary": str, "comments": [...]}."""
    path = Path(target)
    code = path.read_text(encoding="utf-8")
    findings = analyze(target)

    client = client or OpenAI()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(code, findings)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "code_review", "strict": True, "schema": REVIEW_SCHEMA},
        },
    )

    return json.loads(response.choices[0].message.content)
