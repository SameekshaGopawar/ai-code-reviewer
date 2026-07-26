"""Runs the AI code reviewer on changed Python files in a PR and posts the
combined result as a single PR comment via the GitHub CLI (`gh`)."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_code_reviewer.llm_reviewer import review_file  # noqa: E402

SEVERITY_ORDER = {"critical": 0, "warning": 1, "suggestion": 2}
SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E1", "suggestion": "\U0001F535"}


def get_changed_python_files(base_ref: str) -> list[str]:
    subprocess.run(["git", "fetch", "origin", base_ref], check=True)
    diff = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", f"origin/{base_ref}...HEAD", "--", "*.py"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in diff.stdout.splitlines() if f and os.path.exists(f)]


def format_review(file_path: str, review: dict) -> str:
    lines = [f"### `{file_path}`", "", review["summary"], ""]
    comments = sorted(review["comments"], key=lambda c: SEVERITY_ORDER.get(c["severity"], 3))
    for c in comments:
        emoji = SEVERITY_EMOJI.get(c["severity"], "")
        lines.append(f"- {emoji} **{c['severity'].upper()}** (line {c['line']}) **{c['title']}** — {c['comment']}")
    return "\n".join(lines)


def main() -> None:
    pr_number = os.environ.get("PR_NUMBER")
    base_ref = os.environ.get("BASE_REF", "main")

    if not pr_number:
        print("PR_NUMBER not set, nothing to do.")
        return

    changed_files = get_changed_python_files(base_ref)
    if not changed_files:
        print("No changed Python files to review.")
        return

    sections = ["## \U0001F916 AI Code Review", ""]
    for file_path in changed_files:
        print(f"Reviewing {file_path}...")
        try:
            review = review_file(file_path)
        except Exception as exc:  # noqa: BLE001 - report and continue with other files
            sections.append(f"### `{file_path}`\n\n_Review failed: {exc}_\n")
            continue
        sections.append(format_review(file_path, review))
        sections.append("")

    body = "\n".join(sections)
    comment_path = "pr_review_comment.md"
    with open(comment_path, "w", encoding="utf-8") as f:
        f.write(body)

    subprocess.run(["gh", "pr", "comment", pr_number, "--body-file", comment_path], check=True)
    print(f"Posted review comment on PR #{pr_number}.")


if __name__ == "__main__":
    main()
