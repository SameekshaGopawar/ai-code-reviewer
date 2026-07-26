import os
import subprocess
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from post_pr_review import format_review, get_changed_python_files  # noqa: E402


class TestFormatReview:
    def test_formats_summary_and_comments_sorted_by_severity(self):
        review = {
            "summary": "Looks mostly fine.",
            "comments": [
                {"line": 5, "severity": "suggestion", "title": "Nit", "comment": "Minor style thing."},
                {"line": 2, "severity": "critical", "title": "Bug", "comment": "This will crash."},
            ],
        }

        out = format_review("foo.py", review)

        assert "`foo.py`" in out
        assert "Looks mostly fine." in out
        assert out.index("CRITICAL") < out.index("SUGGESTION")
        assert "line 2" in out
        assert "line 5" in out

    def test_handles_no_comments(self):
        review = {"summary": "All good.", "comments": []}
        out = format_review("foo.py", review)
        assert "All good." in out


class TestGetChangedPythonFiles:
    def test_returns_only_existing_python_files_from_diff(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "kept.py").write_text("x = 1\n")

        def fake_run(cmd, **kwargs):
            if cmd[:2] == ["git", "fetch"]:
                return subprocess.CompletedProcess(cmd, 0)
            return subprocess.CompletedProcess(cmd, 0, stdout="kept.py\ndeleted.py\n")

        with patch("post_pr_review.subprocess.run", side_effect=fake_run):
            files = get_changed_python_files("main")

        assert files == ["kept.py"]
