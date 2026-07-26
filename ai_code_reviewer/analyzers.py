"""Wrappers around pylint, flake8, and bandit that normalize their output
into a common list-of-findings structure for downstream (LLM) consumption."""
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Finding:
    tool: str
    file: str
    line: int
    column: int
    code: str
    message: str
    severity: str  # "suggestion" | "warning" | "critical"


_PYLINT_SEVERITY = {
    "convention": "suggestion",
    "refactor": "suggestion",
    "warning": "warning",
    "error": "critical",
    "fatal": "critical",
}

_FLAKE8_LINE_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>\w+) (?P<message>.+)$")

_BANDIT_SEVERITY = {
    "LOW": "suggestion",
    "MEDIUM": "warning",
    "HIGH": "critical",
}


def _run(cmd: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", *cmd],
        capture_output=True,
        text=True,
    )
    return result.stdout


def run_pylint(target: str) -> list[Finding]:
    output = _run(["pylint", "--output-format=json", target])
    if not output.strip():
        return []
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return []
    findings = []
    for item in raw:
        findings.append(Finding(
            tool="pylint",
            file=item.get("path", target),
            line=item.get("line", 0),
            column=item.get("column", 0),
            code=item.get("message-id", ""),
            message=item.get("message", ""),
            severity=_PYLINT_SEVERITY.get(item.get("type", ""), "warning"),
        ))
    return findings


def run_flake8(target: str) -> list[Finding]:
    output = _run(["flake8", target])
    findings = []
    for line in output.splitlines():
        match = _FLAKE8_LINE_RE.match(line)
        if not match:
            continue
        code = match.group("code")
        severity = "warning" if code.startswith(("E", "W", "C")) else "suggestion"
        if code.startswith("F"):
            severity = "critical"  # pyflakes codes usually indicate real bugs
        findings.append(Finding(
            tool="flake8",
            file=match.group("path"),
            line=int(match.group("line")),
            column=int(match.group("col")),
            code=code,
            message=match.group("message"),
            severity=severity,
        ))
    return findings


def run_bandit(target: str) -> list[Finding]:
    output = _run(["bandit", "-f", "json", "-r", target])
    if not output.strip():
        return []
    try:
        raw = json.loads(output)
    except json.JSONDecodeError:
        return []
    findings = []
    for item in raw.get("results", []):
        findings.append(Finding(
            tool="bandit",
            file=item.get("filename", target),
            line=item.get("line_number", 0),
            column=0,
            code=item.get("test_id", ""),
            message=item.get("issue_text", ""),
            severity=_BANDIT_SEVERITY.get(item.get("issue_severity", ""), "warning"),
        ))
    return findings


def analyze(target: str) -> list[dict]:
    """Run all three analyzers against a file or directory and return
    a flat list of finding dicts, sorted by file then line number."""
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(target)

    findings = [
        *run_pylint(target),
        *run_flake8(target),
        *run_bandit(target),
    ]
    findings.sort(key=lambda f: (f.file, f.line))
    return [asdict(f) for f in findings]
