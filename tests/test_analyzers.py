import json
from unittest.mock import patch

import pytest

from ai_code_reviewer.analyzers import analyze, run_bandit, run_flake8, run_pylint


def _mock_run(stdout):
    result = type("Result", (), {"stdout": stdout})()
    return result


class TestRunPylint:
    def test_parses_findings_and_maps_severity(self):
        raw = json.dumps([
            {"path": "foo.py", "line": 3, "column": 0, "message-id": "C0114",
             "message": "Missing module docstring", "type": "convention"},
            {"path": "foo.py", "line": 10, "column": 4, "message-id": "E0001",
             "message": "Syntax error", "type": "error"},
        ])
        with patch("ai_code_reviewer.analyzers._run", return_value=raw):
            findings = run_pylint("foo.py")

        assert len(findings) == 2
        assert findings[0].tool == "pylint"
        assert findings[0].severity == "suggestion"
        assert findings[1].severity == "critical"

    def test_empty_output_returns_no_findings(self):
        with patch("ai_code_reviewer.analyzers._run", return_value=""):
            assert run_pylint("foo.py") == []

    def test_invalid_json_returns_no_findings(self):
        with patch("ai_code_reviewer.analyzers._run", return_value="not json"):
            assert run_pylint("foo.py") == []


class TestRunFlake8:
    def test_parses_lines_and_maps_severity(self):
        output = (
            "foo.py:1:1: F401 'os' imported but unused\n"
            "foo.py:5:1: E501 line too long\n"
            "foo.py:9:1: C901 too complex\n"
        )
        with patch("ai_code_reviewer.analyzers._run", return_value=output):
            findings = run_flake8("foo.py")

        assert len(findings) == 3
        assert findings[0].code == "F401"
        assert findings[0].severity == "critical"
        assert findings[1].severity == "warning"
        assert findings[2].severity == "warning"

    def test_unmatched_lines_are_skipped(self):
        with patch("ai_code_reviewer.analyzers._run", return_value="not a finding line"):
            assert run_flake8("foo.py") == []


class TestRunBandit:
    def test_parses_findings_and_maps_severity(self):
        raw = json.dumps({"results": [
            {"filename": "foo.py", "line_number": 2, "test_id": "B404",
             "issue_text": "subprocess module", "issue_severity": "LOW"},
            {"filename": "foo.py", "line_number": 11, "test_id": "B602",
             "issue_text": "shell=True", "issue_severity": "HIGH"},
        ]})
        with patch("ai_code_reviewer.analyzers._run", return_value=raw):
            findings = run_bandit("foo.py")

        assert len(findings) == 2
        assert findings[0].severity == "suggestion"
        assert findings[1].severity == "critical"

    def test_empty_output_returns_no_findings(self):
        with patch("ai_code_reviewer.analyzers._run", return_value=""):
            assert run_bandit("foo.py") == []


class TestAnalyze:
    def test_raises_for_missing_target(self):
        with pytest.raises(FileNotFoundError):
            analyze("does_not_exist.py")

    def test_combines_and_sorts_all_tools(self, tmp_path):
        target = tmp_path / "foo.py"
        target.write_text("import os\n")

        pylint_out = json.dumps([
            {"path": str(target), "line": 5, "column": 0, "message-id": "C0114",
             "message": "Missing docstring", "type": "convention"},
        ])
        bandit_out = json.dumps({"results": [
            {"filename": str(target), "line_number": 1, "test_id": "B404",
             "issue_text": "subprocess", "issue_severity": "LOW"},
        ]})
        flake8_out = f"{target}:3:1: F401 'os' imported but unused\n"

        def fake_run(cmd):
            if "pylint" in cmd:
                return pylint_out
            if "flake8" in cmd:
                return flake8_out
            if "bandit" in cmd:
                return bandit_out
            return ""

        with patch("ai_code_reviewer.analyzers._run", side_effect=fake_run):
            findings = analyze(str(target))

        assert [f["line"] for f in findings] == [1, 3, 5]
        assert {f["tool"] for f in findings} == {"pylint", "flake8", "bandit"}
