#!/usr/bin/env python3
"""
Reviews Log Manager
===================

MANDATORY wrapper for all reviews.json operations.
Agents MUST NOT edit reviews.json directly.

This file is an APPEND-ONLY LOG. Reviews and fixes can only be added, never modified.

Commands:
    init            Initialize reviews.json
    add-review      Add a new review entry
    add-fix         Add a new fix entry
    get-review      Get a specific review
    get-last        Get the last review (or specific field with --field)
    get-fix-count   Get fix attempt count for a feature
    show-issues     Show issues from last review formatted for fixing
    list            List all reviews and fixes
    mark-merged     Mark a fix as merged to main

Field Access (no Python parsing needed):
    python3 scripts/reviews.py get-last --field review_id
    python3 scripts/reviews.py get-last --field verdict
    python3 scripts/reviews.py get-last --field issues
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_reviews(path: Path) -> dict:
    """Load reviews.json."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_reviews(path: Path, data: dict) -> None:
    """Save reviews.json with backup."""
    backup_dir = path.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"reviews_{timestamp}.json"

    if path.exists():
        with open(path) as f:
            backup_data = f.read()
        with open(backup_path, "w") as f:
            f.write(backup_data)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def cmd_init(args) -> None:
    """Initialize reviews.json."""
    path = args.file

    if path.exists() and not args.force:
        print(f"ERROR: {path} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    data = {
        "schema_version": "1.0",
        "reviews": [],
        "fixes": []
    }

    save_reviews(path, data)
    print(f"SUCCESS: Initialized {path}")


def cmd_add_review(args) -> None:
    """Add a new review entry."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist. Run 'init' first.", file=sys.stderr)
        sys.exit(1)

    # Determine next review ID
    reviews = data.get("reviews", [])
    next_id = max([r.get("review_id", 0) for r in reviews], default=0) + 1

    timestamp = get_timestamp()

    # Parse issues from JSON string or file
    issues = []
    if args.issues:
        try:
            issues = json.loads(args.issues)
        except json.JSONDecodeError:
            # Try reading as file
            issues_path = Path(args.issues)
            if issues_path.exists():
                with open(issues_path) as f:
                    issues = json.load(f)
            else:
                print(f"ERROR: Invalid issues JSON: {args.issues}", file=sys.stderr)
                sys.exit(1)

    review = {
        "review_id": next_id,
        "agent_type": args.agent_type,
        "feature_id": args.feature_id,
        "branch": args.branch,
        "timestamp": timestamp,
        "verdict": args.verdict,
        "issues": issues,
        "summary": args.summary,
        "commit_range": {
            "from": args.commit_from,
            "to": args.commit_to
        }
    }

    data["reviews"].append(review)
    save_reviews(args.file, data)

    print(f"SUCCESS: Added review R{next_id}")
    print(json.dumps(review, indent=2))


def cmd_add_fix(args) -> None:
    """Add a new fix entry."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    # Determine next fix ID
    fixes = data.get("fixes", [])
    next_id = max([f.get("fix_id", 0) for f in fixes], default=0) + 1

    timestamp = get_timestamp()

    # Parse issues fixed
    issues_fixed = []
    if args.issues_fixed:
        try:
            issues_fixed = json.loads(args.issues_fixed)
        except json.JSONDecodeError:
            issues_path = Path(args.issues_fixed)
            if issues_path.exists():
                with open(issues_path) as f:
                    issues_fixed = json.load(f)
            else:
                print(f"ERROR: Invalid issues_fixed JSON", file=sys.stderr)
                sys.exit(1)

    # Parse issues deferred
    issues_deferred = []
    if args.issues_deferred:
        try:
            issues_deferred = json.loads(args.issues_deferred)
        except json.JSONDecodeError:
            issues_path = Path(args.issues_deferred)
            if issues_path.exists():
                with open(issues_path) as f:
                    issues_deferred = json.load(f)

    # Parse tests added
    tests_added = args.tests_added.split(",") if args.tests_added else []
    tests_added = [t.strip() for t in tests_added if t.strip()]

    fix = {
        "fix_id": next_id,
        "review_id": args.review_id,
        "feature_id": args.feature_id,
        "branch": args.branch,
        "agent_type": "FIX",
        "timestamp": timestamp,
        "issues_fixed": issues_fixed,
        "issues_deferred": issues_deferred,
        "tests_added": tests_added,
        "merged_to_main": False,
        "pending_review": True
    }

    data["fixes"].append(fix)
    save_reviews(args.file, data)

    print(f"SUCCESS: Added fix F{next_id}")
    print(json.dumps(fix, indent=2))


def cmd_get_review(args) -> None:
    """Get a specific review by ID."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    for review in data.get("reviews", []):
        if review.get("review_id") == args.review_id:
            print(json.dumps(review, indent=2))
            return

    print(f"ERROR: Review R{args.review_id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_get_last(args) -> None:
    """Get the last review or a specific field from it."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    reviews = data.get("reviews", [])
    if not reviews:
        print("ERROR: No reviews found", file=sys.stderr)
        sys.exit(1)

    review = reviews[-1]

    # If a specific field is requested, return just that value
    if args.field:
        field = args.field
        value = review.get(field)
        if value is None:
            print("")
        elif isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2))
        else:
            print(value)
        return

    print(json.dumps(review, indent=2))


def cmd_get_fix_count(args) -> None:
    """Get fix attempt count for a feature."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    fixes = data.get("fixes", [])
    count = len([f for f in fixes if f.get("feature_id") == args.feature_id])

    print(f"FIX_COUNT: {count}")
    print(f"REMAINING: {3 - count}")

    if count >= 2:
        print("WARNING: FINAL FIX ATTEMPT - Next failure triggers mandatory decision")
    elif count >= 3:
        print("ERROR: Maximum fix attempts reached - Tiebreaker required")


def cmd_show_issues(args) -> None:
    """Show issues from the last review in a formatted list."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    reviews = data.get("reviews", [])
    if not reviews:
        print("ERROR: No reviews found", file=sys.stderr)
        sys.exit(1)

    review = reviews[-1]
    issues = review.get("issues", [])

    if not issues:
        print("NO_ISSUES: Review has no issues to fix")
        return

    print("=== ISSUES TO FIX ===")
    print(f"Review: R{review.get('review_id')}")
    print(f"Feature: {review.get('feature_id', 'ARCHITECTURE')}")
    print(f"Verdict: {review.get('verdict')}")
    print()

    # Group by severity
    severity_order = ["critical", "major", "minor", "suggestion"]
    for severity in severity_order:
        severity_issues = [i for i in issues if i.get("severity", "").lower() == severity]
        if severity_issues:
            print(f"--- {severity.upper()} ({len(severity_issues)}) ---")
            for issue in severity_issues:
                print(f"  [{issue.get('id')}] {issue.get('description')}")
                if issue.get('location'):
                    print(f"    Location: {issue.get('location')}")
                if issue.get('suggestion'):
                    print(f"    Fix: {issue.get('suggestion')}")
                print()


def cmd_list(args) -> None:
    """List all reviews and fixes."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    print("=== REVIEWS ===")
    for review in data.get("reviews", []):
        rid = review.get("review_id")
        verdict = review.get("verdict")
        feature = review.get("feature_id", "ARCHITECTURE")
        agent = review.get("agent_type")
        issue_count = len(review.get("issues", []))
        print(f"  R{rid}: [{agent}] {feature} - {verdict} ({issue_count} issues)")

    print("\n=== FIXES ===")
    for fix in data.get("fixes", []):
        fid = fix.get("fix_id")
        review_id = fix.get("review_id")
        feature = fix.get("feature_id", "ARCHITECTURE")
        fixed = len(fix.get("issues_fixed", []))
        deferred = len(fix.get("issues_deferred", []))
        pending = "PENDING" if fix.get("pending_review") else "VERIFIED"
        print(f"  F{fid}: addresses R{review_id} for {feature} - {fixed} fixed, {deferred} deferred [{pending}]")


def cmd_mark_merged(args) -> None:
    """Mark a fix as merged to main."""
    data = load_reviews(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    for fix in data.get("fixes", []):
        if fix.get("fix_id") == args.fix_id:
            fix["merged_to_main"] = True
            fix["pending_review"] = False
            fix["merged_at"] = get_timestamp()
            save_reviews(args.file, data)
            print(f"SUCCESS: Fix F{args.fix_id} marked as merged")
            return

    print(f"ERROR: Fix F{args.fix_id} not found", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Reviews log manager - MANDATORY for all review operations"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=Path("reviews.json"),
        help="Path to reviews.json"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize reviews.json")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing file")

    # add-review
    add_review_parser = subparsers.add_parser("add-review", help="Add review entry")
    add_review_parser.add_argument("--agent-type", "-a", required=True,
                                   choices=["REVIEW", "ARCHITECTURE"],
                                   help="Review agent type")
    add_review_parser.add_argument("--feature-id", help="Feature ID (null for architecture)")
    add_review_parser.add_argument("--branch", "-b", required=True, help="Branch reviewed")
    add_review_parser.add_argument("--verdict", "-v", required=True,
                                   choices=["APPROVE", "REQUEST_CHANGES", "PASS_WITH_COMMENTS", "REJECT"],
                                   help="Review verdict")
    add_review_parser.add_argument("--issues", help="Issues JSON string or file path")
    add_review_parser.add_argument("--summary", "-s", required=True, help="Review summary")
    add_review_parser.add_argument("--commit-from", help="Starting commit of reviewed range")
    add_review_parser.add_argument("--commit-to", help="Ending commit of reviewed range")

    # add-fix
    add_fix_parser = subparsers.add_parser("add-fix", help="Add fix entry")
    add_fix_parser.add_argument("--review-id", "-r", type=int, required=True, help="Review ID addressed")
    add_fix_parser.add_argument("--feature-id", help="Feature ID")
    add_fix_parser.add_argument("--branch", "-b", required=True, help="Branch with fixes")
    add_fix_parser.add_argument("--issues-fixed", help="Issues fixed JSON string or file")
    add_fix_parser.add_argument("--issues-deferred", help="Issues deferred JSON string or file")
    add_fix_parser.add_argument("--tests-added", help="Comma-separated test names added")

    # get-review
    get_review_parser = subparsers.add_parser("get-review", help="Get review by ID")
    get_review_parser.add_argument("review_id", type=int, help="Review ID")

    # get-last
    get_last_parser = subparsers.add_parser("get-last", help="Get last review")
    get_last_parser.add_argument("--field", help="Get specific field (e.g., review_id, issues, verdict)")

    # get-fix-count
    fix_count_parser = subparsers.add_parser("get-fix-count", help="Get fix count for feature")
    fix_count_parser.add_argument("feature_id", help="Feature ID")

    # show-issues
    subparsers.add_parser("show-issues", help="Show issues from last review formatted for fixing")

    # list
    subparsers.add_parser("list", help="List all reviews and fixes")

    # mark-merged
    mark_parser = subparsers.add_parser("mark-merged", help="Mark fix as merged")
    mark_parser.add_argument("fix_id", type=int, help="Fix ID to mark as merged")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "add-review": cmd_add_review,
        "add-fix": cmd_add_fix,
        "get-review": cmd_get_review,
        "get-last": cmd_get_last,
        "get-fix-count": cmd_get_fix_count,
        "show-issues": cmd_show_issues,
        "list": cmd_list,
        "mark-merged": cmd_mark_merged,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
