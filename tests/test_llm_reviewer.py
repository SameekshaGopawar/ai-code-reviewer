import json
from unittest.mock import MagicMock, patch

from ai_code_reviewer.llm_reviewer import _build_user_message, review_file


def _fake_client(review_dict):
    client = MagicMock()
    message = MagicMock()
    message.content = json.dumps(review_dict)
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    client.chat.completions.create.return_value = response
    return client


class TestBuildUserMessage:
    def test_includes_code_and_findings(self):
        findings = [{"tool": "bandit", "line": 1, "message": "issue"}]
        msg = _build_user_message("print('hi')", findings)

        assert "print('hi')" in msg
        assert "bandit" in msg
        assert "```python" in msg

    def test_handles_no_findings(self):
        msg = _build_user_message("print('hi')", [])
        assert "(none)" in msg


class TestReviewFile:
    def test_returns_parsed_review_using_injected_client(self, tmp_path):
        target = tmp_path / "foo.py"
        target.write_text("import os\n")

        expected = {
            "summary": "Looks fine.",
            "comments": [
                {"line": 1, "severity": "suggestion", "title": "Unused import",
                 "comment": "Remove the unused os import."},
            ],
        }
        client = _fake_client(expected)

        with patch("ai_code_reviewer.llm_reviewer.analyze", return_value=[]):
            result = review_file(str(target), client=client)

        assert result == expected
        client.chat.completions.create.assert_called_once()

    def test_sends_source_and_findings_to_the_model(self, tmp_path):
        target = tmp_path / "foo.py"
        target.write_text("x = 1\n")

        client = _fake_client({"summary": "ok", "comments": []})
        findings = [{"tool": "pylint", "line": 1, "message": "some finding"}]

        with patch("ai_code_reviewer.llm_reviewer.analyze", return_value=findings):
            review_file(str(target), client=client)

        _, kwargs = client.chat.completions.create.call_args
        user_message = kwargs["messages"][1]["content"]
        assert "x = 1" in user_message
        assert "some finding" in user_message
