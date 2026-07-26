import argparse
import json

from ai_code_reviewer.analyzers import analyze


def _print_review(review: dict) -> None:
    severity_order = {"critical": 0, "warning": 1, "suggestion": 2}
    print(f"Summary: {review['summary']}\n")
    for c in sorted(review["comments"], key=lambda c: severity_order.get(c["severity"], 3)):
        print(f"[{c['severity'].upper()}] line {c['line']}: {c['title']}")
        print(f"  {c['comment']}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run static analysis and emit structured findings.")
    parser.add_argument("target", help="File or directory to analyze")
    parser.add_argument("-o", "--output", help="Write JSON output to this file instead of stdout")
    parser.add_argument("--review", action="store_true", help="Also run the LLM review pipeline (single file only)")
    args = parser.parse_args()

    if args.review:
        from ai_code_reviewer.llm_reviewer import review_file

        review = review_file(args.target)
        output_json = json.dumps(review, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json)
            print(f"Wrote review to {args.output}")
        else:
            _print_review(review)
        return

    findings = analyze(args.target)
    output_json = json.dumps(findings, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Wrote {len(findings)} findings to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
