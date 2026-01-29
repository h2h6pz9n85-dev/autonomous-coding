#!/usr/bin/env python3
"""
Feature List Manager
====================

MANDATORY wrapper for all feature_list.json operations.
Agents MUST NOT edit feature_list.json directly.

Commands:
    next        Get the next feature to implement (first with passes=false)
    get <id>    Get details of a specific feature
    pass <id>   Mark a feature as passing (REVIEW agent only)
    list        List all features with status
    stats       Show feature statistics
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_features(path: Path) -> dict:
    """Load feature_list.json."""
    if not path.exists():
        print(f"ERROR: {path} does not exist", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_features(path: Path, data: dict) -> None:
    """Save feature_list.json with backup."""
    # Create backup
    backup_dir = path.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"feature_list_{timestamp}.json"

    if path.exists():
        with open(path) as f:
            backup_data = f.read()
        with open(backup_path, "w") as f:
            f.write(backup_data)

    # Save new data
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def cmd_next(args) -> None:
    """Get the next feature to implement."""
    data = load_features(args.file)

    for feature in data.get("features", []):
        if not feature.get("passes", False):
            print(json.dumps(feature, indent=2))
            return

    print("NO_MORE_FEATURES: All features are passing!", file=sys.stderr)
    sys.exit(0)


def cmd_next_candidates(args) -> None:
    """Get up to N pending features for the agent to choose from.
    
    Returns pending features so the agent can intelligently select
    which ones to work on together (up to 5 at a time).
    """
    data = load_features(args.file)
    count = args.count
    
    pending_features = [f for f in data.get("features", []) if not f.get("passes", False)]
    
    if not pending_features:
        print("NO_MORE_FEATURES: All features are passing!", file=sys.stderr)
        sys.exit(0)
    
    # Return up to N candidates for the agent to choose from
    candidates = pending_features[:count]
    
    result = {
        "total_pending": len(pending_features),
        "candidates_shown": len(candidates),
        "features": candidates,
        "instruction": "Select up to 5 RELATED features to implement together. Choose features that share the same component, category, or have dependencies on each other."
    }
    print(json.dumps(result, indent=2))


def cmd_get(args) -> None:
    """Get a specific feature by ID."""
    data = load_features(args.file)

    for feature in data.get("features", []):
        if feature.get("id") == args.feature_id:
            print(json.dumps(feature, indent=2))
            return

    print(f"ERROR: Feature {args.feature_id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_pass(args) -> None:
    """Mark a feature as passing. REVIEW agent only."""
    data = load_features(args.file)

    found = False
    for feature in data.get("features", []):
        if feature.get("id") == args.feature_id:
            if feature.get("passes", False):
                print(f"WARNING: Feature {args.feature_id} is already passing", file=sys.stderr)
            feature["passes"] = True
            feature["passed_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break

    if not found:
        print(f"ERROR: Feature {args.feature_id} not found", file=sys.stderr)
        sys.exit(1)

    save_features(args.file, data)
    print(f"SUCCESS: Feature {args.feature_id} marked as PASSING")


def cmd_pass_batch(args) -> None:
    """Mark multiple features as passing. REVIEW agent only.
    
    Args:
        feature_ids: Comma-separated list of feature IDs (e.g., "F001,F002,F003")
    """
    data = load_features(args.file)
    feature_ids = [fid.strip() for fid in args.feature_ids.split(",")]
    
    passed = []
    not_found = []
    already_passing = []
    
    for feature in data.get("features", []):
        if feature.get("id") in feature_ids:
            if feature.get("passes", False):
                already_passing.append(feature.get("id"))
            else:
                feature["passes"] = True
                feature["passed_at"] = datetime.now(timezone.utc).isoformat()
                passed.append(feature.get("id"))
            feature_ids.remove(feature.get("id"))
    
    not_found = feature_ids  # Remaining IDs not found
    
    if not_found:
        print(f"ERROR: Features not found: {', '.join(not_found)}", file=sys.stderr)
        sys.exit(1)
    
    save_features(args.file, data)
    
    if already_passing:
        print(f"WARNING: Already passing: {', '.join(already_passing)}", file=sys.stderr)
    print(f"SUCCESS: Marked {len(passed)} features as PASSING: {', '.join(passed)}")


def cmd_fail(args) -> None:
    """Mark a feature as failing (regression detected)."""
    data = load_features(args.file)

    found = False
    for feature in data.get("features", []):
        if feature.get("id") == args.feature_id:
            feature["passes"] = False
            feature["failed_at"] = datetime.now(timezone.utc).isoformat()
            feature["failure_reason"] = args.reason
            found = True
            break

    if not found:
        print(f"ERROR: Feature {args.feature_id} not found", file=sys.stderr)
        sys.exit(1)

    save_features(args.file, data)
    print(f"SUCCESS: Feature {args.feature_id} marked as FAILING - {args.reason}")


def cmd_list(args) -> None:
    """List all features with status."""
    data = load_features(args.file)

    for feature in data.get("features", []):
        status = "PASS" if feature.get("passes", False) else "FAIL"
        print(f"[{status}] {feature['id']}: {feature['name']}")


def cmd_stats(args) -> None:
    """Show feature statistics."""
    data = load_features(args.file)
    features = data.get("features", [])

    total = len(features)
    passing = sum(1 for f in features if f.get("passes", False))
    failing = total - passing

    print(f"Total features: {total}")
    print(f"Passing: {passing}")
    print(f"Failing: {failing}")
    print(f"Progress: {passing}/{total} ({100*passing//total if total else 0}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Feature list manager - MANDATORY for all feature operations"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=Path("feature_list.json"),
        help="Path to feature_list.json"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # next
    subparsers.add_parser("next", help="Get next feature to implement")

    # next-candidates
    next_candidates_parser = subparsers.add_parser("next-candidates", help="Get pending features for agent to choose from (up to 5)")
    next_candidates_parser.add_argument("--count", "-c", type=int, default=15, help="Number of candidates to show (default: 15)")

    # get
    get_parser = subparsers.add_parser("get", help="Get feature by ID")
    get_parser.add_argument("feature_id", help="Feature ID (e.g., F001)")

    # pass
    pass_parser = subparsers.add_parser("pass", help="Mark feature as passing")
    pass_parser.add_argument("feature_id", help="Feature ID to mark as passing")

    # pass-batch
    pass_batch_parser = subparsers.add_parser("pass-batch", help="Mark multiple features as passing")
    pass_batch_parser.add_argument("feature_ids", help="Comma-separated feature IDs (e.g., F001,F002,F003)")

    # fail
    fail_parser = subparsers.add_parser("fail", help="Mark feature as failing (regression)")
    fail_parser.add_argument("feature_id", help="Feature ID to mark as failing")
    fail_parser.add_argument("--reason", "-r", required=True, help="Reason for failure")

    # list
    subparsers.add_parser("list", help="List all features")

    # stats
    subparsers.add_parser("stats", help="Show statistics")

    args = parser.parse_args()

    commands = {
        "next": cmd_next,
        "next-candidates": cmd_next_candidates,
        "get": cmd_get,
        "pass": cmd_pass,
        "pass-batch": cmd_pass_batch,
        "fail": cmd_fail,
        "list": cmd_list,
        "stats": cmd_stats,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
