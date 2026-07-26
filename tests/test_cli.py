import json
import subprocess
import sys
from unittest.mock import patch

from ai_code_reviewer.cli import main


def test_main_analyze_mode_prints_json(tmp_path, capsys, monkeypatch):
    target = tmp_path / "foo.py"
    target.write_text("import os\n")

    monkeypatch.setattr(sys, "argv", ["ai-code-reviewer", str(target)])
    main()

    findings = json.loads(capsys.readouterr().out)
    assert isinstance(findings, list)
    assert any(f["code"] in ("F401", "W0611") for f in findings)


def test_main_analyze_mode_writes_output_file(tmp_path, capsys, monkeypatch):
    target = tmp_path / "foo.py"
    target.write_text("import os\n")
    out_file = tmp_path / "out.json"

    monkeypatch.setattr(sys, "argv", ["ai-code-reviewer", str(target), "-o", str(out_file)])
    main()

    assert f"Wrote" in capsys.readouterr().out
    findings = json.loads(out_file.read_text())
    assert isinstance(findings, list)


def test_main_review_mode_prints_summary_and_comments(tmp_path, capsys, monkeypatch):
    target = tmp_path / "foo.py"
    target.write_text("import os\n")

    fake_review = {
        "summary": "Looks fine.",
        "comments": [
            {"line": 1, "severity": "critical", "title": "Bad thing", "comment": "Fix it."},
            {"line": 2, "severity": "suggestion", "title": "Nit", "comment": "Minor."},
        ],
    }
    monkeypatch.setattr(sys, "argv", ["ai-code-reviewer", str(target), "--review"])

    with patch("ai_code_reviewer.llm_reviewer.review_file", return_value=fake_review):
        main()

    out = capsys.readouterr().out
    assert "Looks fine." in out
    assert "[CRITICAL] line 1: Bad thing" in out
    assert "[SUGGESTION] line 2: Nit" in out
    assert out.index("CRITICAL") < out.index("SUGGESTION")


def test_main_review_mode_writes_output_file(tmp_path, monkeypatch):
    target = tmp_path / "foo.py"
    target.write_text("import os\n")
    out_file = tmp_path / "review.json"

    fake_review = {"summary": "ok", "comments": []}
    monkeypatch.setattr(
        sys, "argv", ["ai-code-reviewer", str(target), "--review", "-o", str(out_file)]
    )

    with patch("ai_code_reviewer.llm_reviewer.review_file", return_value=fake_review):
        main()

    assert json.loads(out_file.read_text()) == fake_review


def test_analyze_only_mode_prints_findings_json(tmp_path):
    target = tmp_path / "foo.py"
    target.write_text("import os\n")

    result = subprocess.run(
        [sys.executable, "-m", "ai_code_reviewer.cli", str(target)],
        capture_output=True,
        text=True,
        check=True,
    )

    findings = json.loads(result.stdout)
    assert isinstance(findings, list)
    assert any(f["code"] in ("F401", "W0611") for f in findings)


def test_missing_target_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "ai_code_reviewer.cli", "no_such_file.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
