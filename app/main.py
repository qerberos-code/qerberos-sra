import argparse
import json
import sys
from datetime import datetime, timezone

import anthropic
from dotenv import load_dotenv

from . import config
from .db import init_db, insert_scan, insert_findings
from .manager import ReviewManager, _run_subagents_parallel
from .remediation import RemediationAgent


def review_repo(
    repo_path: str,
    output_dir: str = "security-review",
    prompt: str | None = None,
    remediate: bool = False,
    db_path: str | None = None,
) -> str:
    """Orchestrate a full multi-agent security review and return the final summary."""
    load_dotenv()
    client = anthropic.Anthropic()

    if db_path is None:
        db_path = f"{output_dir}/db.sqlite"
    init_db(db_path)

    print("Running sub-agents in parallel…", file=sys.stderr)
    subagent_results = _run_subagents_parallel(client, repo_path)

    print("Manager synthesizing findings…", file=sys.stderr)
    summary = ReviewManager().orchestrate(
        client, repo_path, output_dir, subagent_results, prompt
    )

    # Persist all findings to the database
    all_findings = [
        f for r in subagent_results.values() for f in r.get("findings", [])
    ]
    scanner_status = {
        name: r.get("scanner_status", {})
        for name, r in subagent_results.items()
    }
    scan_id = insert_scan(repo_path, config.MANAGER_MODEL, scanner_status, db_path)
    if all_findings:
        insert_findings(scan_id, all_findings, db_path)

    # Persist raw findings JSON as a timestamped backup
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    findings_path = f"{output_dir}/findings-{ts}.json"
    try:
        import os; os.makedirs(output_dir, exist_ok=True)
        with open(findings_path, "w") as f:
            json.dump(subagent_results, f, indent=2)
    except Exception:
        pass

    if remediate:
        print("\n--- Remediation pass ---", file=sys.stderr)
        rem_summary = RemediationAgent().apply_fixes(client, repo_path, all_findings, db_path)
        summary = summary + "\n\n## Remediation\n" + rem_summary

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent security review: scan, prioritize, report, remediate."
    )
    parser.add_argument(
        "repo_path", nargs="?", default=".", help="Path to the repository to review"
    )
    parser.add_argument(
        "-o", "--output-dir", default="security-review",
        help="Directory to write reports into (default: security-review)",
    )
    parser.add_argument("-p", "--prompt", help="Extra instructions for the reviewer")
    parser.add_argument(
        "--remediate", action="store_true",
        help="Auto-apply fixes and open PRs for CRITICAL/HIGH findings",
    )
    args = parser.parse_args()
    print(review_repo(args.repo_path, args.output_dir, args.prompt, args.remediate))


if __name__ == "__main__":
    main()
