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
    """Get the next item to work on, optionally filtered by type."""
    data = load_features(args.file)
    filter_type = getattr(args, 'type', None)

    for feature in data.get("features", []):
        if feature.get("passes", False):
            continue

        # Filter by type if specified
        if filter_type:
            item_type = feature.get("type")
            filter_upper = filter_type.upper()

            if filter_upper == "BUG" and item_type != "bug":
                continue
            if filter_upper == "DEBT" and item_type != "tech_debt":
                continue
            if filter_upper == "FEAT" and item_type in ("bug", "tech_debt"):
                continue

        print(json.dumps(feature, indent=2))
        return

    if filter_type:
        print(f"NO_MORE_{filter_type.upper()}: All {filter_type}s are passing!", file=sys.stderr)
    else:
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
    """List all features with status, grouped by priority."""
    data = load_features(args.file)
    features = data.get("features", [])

    # Categorize features
    in_progress = []
    pending_bugs = []
    pending_debt = []
    pending_features = []
    passing = []

    for f in features:
        if f.get("passes", False):
            passing.append(f)
        elif f.get("type") == "bug":
            pending_bugs.append(f)
        elif f.get("type") == "tech_debt":
            pending_debt.append(f)
        else:
            pending_features.append(f)

    # Print in priority order
    if in_progress:
        print("=== IN PROGRESS ===")
        for f in in_progress:
            print(f"{f['id']}: {f['name']} [in-progress]")
        print()

    if pending_bugs:
        print("=== BUGS (priority) ===")
        for f in pending_bugs:
            print(f"{f['id']}: {f['name']} [pending]")
        print()

    if pending_debt:
        print(f"=== TECH DEBT ({len(pending_debt)} items) ===")
        for f in pending_debt:
            source = f.get("source_review", "unknown")
            print(f"{f['id']}: {f['name']} [pending] (from {source})")
        print()

    if pending_features:
        print("=== FEATURES ===")
        for f in pending_features:
            print(f"{f['id']}: {f['name']} [pending]")
        print()

    if passing:
        print("=== PASSING ===")
        for f in passing:
            print(f"{f['id']}: {f['name']} [pass]")
        print()

    # Summary
    print(f"Summary: {len(pending_bugs)} bugs, {len(pending_debt)} tech debt, {len(pending_features)} features pending, {len(passing)} passing")


def cmd_stats(args) -> None:
    """Show feature statistics."""
    data = load_features(args.file)
    features = data.get("features", [])

    total = len(features)
    passing = sum(1 for f in features if f.get("passes", False))
    failing = total - passing

    # Count by type (features vs bugs vs tech debt)
    feature_entries = [f for f in features if f.get("type") not in ("bug", "tech_debt")]
    bug_entries = [f for f in features if f.get("type") == "bug"]
    debt_entries = [f for f in features if f.get("type") == "tech_debt"]

    features_passing = sum(1 for f in feature_entries if f.get("passes", False))
    bugs_resolved = sum(1 for f in bug_entries if f.get("passes", False))
    debt_resolved = sum(1 for f in debt_entries if f.get("passes", False))

    print(f"Features: {features_passing}/{len(feature_entries)} passing")
    print(f"Bugs: {bugs_resolved}/{len(bug_entries)} resolved")
    print(f"Tech Debt: {debt_resolved}/{len(debt_entries)} resolved")
    print(f"Total: {passing}/{total} ({100*passing//total if total else 0}%)")

    # Show next work item (priority: bugs > tech_debt threshold > features)
    pending_bugs = [f for f in bug_entries if not f.get("passes", False)]
    pending_debt = [f for f in debt_entries if not f.get("passes", False)]
    pending_features = [f for f in feature_entries if not f.get("passes", False)]

    if pending_bugs:
        print(f"Next: {pending_bugs[0]['id']} (bug - priority)")
    elif len(pending_debt) >= 5:
        print(f"Next: GLOBAL_FIX ({len(pending_debt)} tech debt items accumulated)")
    elif pending_features:
        print(f"Next: {pending_features[0]['id']}")
    elif pending_debt:
        print(f"Next: {pending_debt[0]['id']} (tech debt)")
    else:
        print("Next: All done!")


def cmd_next_id(args) -> None:
    """Get the next available ID for a given type (FEAT, BUG, or DEBT)."""
    data = load_features(args.file)
    features = data.get("features", [])

    id_type = args.type.upper()
    if id_type not in ("FEAT", "BUG", "DEBT"):
        print(f"ERROR: Type must be FEAT, BUG, or DEBT, got: {id_type}", file=sys.stderr)
        sys.exit(1)

    prefix = f"{id_type}-"
    max_num = 0

    for feature in features:
        fid = feature.get("id", "")
        if fid.startswith(prefix):
            try:
                num = int(fid[len(prefix):])
                max_num = max(max_num, num)
            except ValueError:
                pass
        # Also check legacy F### format for features
        elif id_type == "FEAT" and fid.startswith("F") and not fid.startswith("FEAT-"):
            try:
                num = int(fid[1:])
                max_num = max(max_num, num)
            except ValueError:
                pass

    next_num = max_num + 1
    print(f"{prefix}{next_num:03d}")


def cmd_debt_count(args) -> None:
    """Get count of pending tech debt items."""
    data = load_features(args.file)
    features = data.get("features", [])

    pending_debt = [
        f for f in features
        if f.get("type") == "tech_debt" and not f.get("passes", False)
    ]

    print(len(pending_debt))


def cmd_append(args) -> None:
    """Append new entries to feature_list.json.

    Used by BROWNFIELD_INITIALIZER to add features/bugs from freeform input.
    """
    data = load_features(args.file)

    try:
        entries = json.loads(args.entries)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in --entries: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(entries, list):
        print("ERROR: --entries must be a JSON array", file=sys.stderr)
        sys.exit(1)

    source_appspec = args.source_appspec

    added_ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            print(f"ERROR: Each entry must be an object, got: {type(entry)}", file=sys.stderr)
            sys.exit(1)

        # Add source appspec reference
        entry["source_appspec"] = source_appspec

        # Ensure passes is false for new entries
        if "passes" not in entry:
            entry["passes"] = False

        data["features"].append(entry)
        added_ids.append(entry.get("id", "UNKNOWN"))

    # Update totals
    features = data.get("features", [])
    data["total_features"] = sum(1 for f in features if f.get("id", "").startswith("FEAT-") or (f.get("id", "").startswith("F") and not f.get("id", "").startswith("FEAT-")))
    data["total_bugs"] = sum(1 for f in features if f.get("id", "").startswith("BUG-"))

    save_features(args.file, data)
    print(f"SUCCESS: Appended {len(added_ids)} entries: {', '.join(added_ids)}")


def main():
    parser = argparse.ArgumentParser(
        description="Feature list manager - MANDATORY for all feature operations"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=None,
        help="Path to feature_list.json (overrides --agent-state-dir)"
    )
    parser.add_argument(
        "--agent-state-dir", "-d",
        type=Path,
        default=None,
        help="Agent state directory (feature_list.json will be in this dir)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # next
    next_parser = subparsers.add_parser("next", help="Get next item to work on")
    next_parser.add_argument("--type", "-t", help="Filter by type: BUG or FEAT")

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

    # next-id
    next_id_parser = subparsers.add_parser("next-id", help="Get next available ID for FEAT, BUG, or DEBT")
    next_id_parser.add_argument("--type", "-t", required=True, help="Type: FEAT, BUG, or DEBT")

    # debt-count
    subparsers.add_parser("debt-count", help="Get count of pending tech debt items")

    # append
    append_parser = subparsers.add_parser("append", help="Append entries to feature list (brownfield)")
    append_parser.add_argument("--entries", "-e", required=True, help="JSON array of entries to append")
    append_parser.add_argument("--source-appspec", "-s", required=True, help="Source appspec file name")

    args = parser.parse_args()

    # Resolve file path: --file > --agent-state-dir > AGENT_STATE_DIR env > current dir
    import os
    if args.file is not None:
        pass  # Use explicit file path
    elif args.agent_state_dir is not None:
        args.file = args.agent_state_dir / "feature_list.json"
    elif os.environ.get("AGENT_STATE_DIR"):
        args.file = Path(os.environ["AGENT_STATE_DIR"]) / "feature_list.json"
    else:
        args.file = Path("feature_list.json")  # Default to current directory

    commands = {
        "next": cmd_next,
        "next-candidates": cmd_next_candidates,
        "get": cmd_get,
        "pass": cmd_pass,
        "pass-batch": cmd_pass_batch,
        "fail": cmd_fail,
        "list": cmd_list,
        "stats": cmd_stats,
        "next-id": cmd_next_id,
        "debt-count": cmd_debt_count,
        "append": cmd_append,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
