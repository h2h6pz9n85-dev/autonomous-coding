#!/usr/bin/env python3
"""
Progress Log Manager
====================

MANDATORY wrapper for all progress.json operations.
Agents MUST NOT edit progress.json directly.

This file is an APPEND-ONLY LOG. Sessions can only be added, never modified.
Status updates are tracked as separate entries.

Commands:
    init              Initialize progress.json for a new project
    add-session       Add a new session entry
    update-status     Update the current status
    get-status        Get current status (or specific field with --field)
    get-session       Get a specific session (or specific field with --field)
    get-review-type   Determine if current review is FEATURE or ARCHITECTURE_REFACTOR
    next-session-id   Get the next session ID (current count + 1)
    list              List all sessions

Field Access (no Python parsing needed):
    python3 scripts/progress.py get-status --field current_branch
    python3 scripts/progress.py get-status --field current_feature
    python3 scripts/progress.py get-session -1 --field agent_type
    python3 scripts/progress.py get-session -1 --field commit_range.from
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_progress(path: Path) -> dict:
    """Load progress.json."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_progress(path: Path, data: dict) -> None:
    """Save progress.json with backup."""
    backup_dir = path.parent / ".backups"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"progress_{timestamp}.json"

    if path.exists():
        with open(path) as f:
            backup_data = f.read()
        with open(backup_path, "w") as f:
            f.write(backup_data)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_git_commit() -> str:
    """Get current git HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def get_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def cmd_init(args) -> None:
    """Initialize progress.json for a new project."""
    path = args.file

    if path.exists() and not args.force:
        print(f"ERROR: {path} already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    commit = get_git_commit()
    timestamp = get_timestamp()

    data = {
        "project": {
            "name": args.project_name,
            "created_at": timestamp,
            "total_features": args.feature_count
        },
        "status": {
            "updated_at": timestamp,
            "features_completed": 0,
            "features_passing": 0,
            "current_phase": "IMPLEMENT",
            "current_feature": None,
            "current_branch": None,
            "head_commit": commit
        },
        "sessions": []
    }

    save_progress(path, data)
    print(f"SUCCESS: Initialized {path}")
    print(json.dumps(data, indent=2))


def cmd_add_session(args) -> None:
    """Add a new session entry."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist. Run 'init' first.", file=sys.stderr)
        sys.exit(1)

    # Determine next session ID
    sessions = data.get("sessions", [])
    next_id = max([s.get("session_id", 0) for s in sessions], default=0) + 1

    timestamp = get_timestamp()
    commit = get_git_commit()

    # Parse commits if provided
    commits = []
    if args.commits:
        for c in args.commits:
            if ":" in c:
                hash_val, msg = c.split(":", 1)
                commits.append({"hash": hash_val.strip(), "message": msg.strip()})
            else:
                commits.append({"hash": c.strip(), "message": ""})

    # Parse features touched
    features_touched = args.features.split(",") if args.features else []
    features_touched = [f.strip() for f in features_touched if f.strip()]

    session = {
        "session_id": next_id,
        "agent_type": args.agent_type,
        "started_at": args.started_at or timestamp,
        "completed_at": timestamp,
        "summary": args.summary,
        "features_touched": features_touched,
        "outcome": args.outcome,
        "commits": commits,
        "commit_range": {
            "from": args.commit_from,
            "to": args.commit_to or commit
        }
    }

    data["sessions"].append(session)

    # Update status
    data["status"]["updated_at"] = timestamp
    data["status"]["head_commit"] = commit

    if args.next_phase:
        data["status"]["current_phase"] = args.next_phase
    if args.current_feature is not None:
        data["status"]["current_feature"] = args.current_feature if args.current_feature != "null" else None
    if args.current_branch is not None:
        data["status"]["current_branch"] = args.current_branch if args.current_branch != "null" else None

    save_progress(args.file, data)
    print(f"SUCCESS: Added session {next_id}")
    print(json.dumps(session, indent=2))


def cmd_update_status(args) -> None:
    """Update current status."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    timestamp = get_timestamp()
    commit = get_git_commit()

    data["status"]["updated_at"] = timestamp
    data["status"]["head_commit"] = commit

    if args.phase:
        data["status"]["current_phase"] = args.phase
    if args.feature is not None:
        data["status"]["current_feature"] = args.feature if args.feature != "null" else None
    if args.branch is not None:
        data["status"]["current_branch"] = args.branch if args.branch != "null" else None
    if args.features_completed is not None:
        data["status"]["features_completed"] = args.features_completed
    if args.features_passing is not None:
        data["status"]["features_passing"] = args.features_passing

    save_progress(args.file, data)
    print("SUCCESS: Status updated")
    print(json.dumps(data["status"], indent=2))


def cmd_get_status(args) -> None:
    """Get current status or a specific field."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    status = data["status"]

    # If a specific field is requested, return just that value
    if args.field:
        field = args.field
        if field not in status:
            print(f"ERROR: Unknown field '{field}'", file=sys.stderr)
            print(f"Available fields: {', '.join(status.keys())}", file=sys.stderr)
            sys.exit(1)
        value = status[field]
        # Print raw value (empty string for None)
        print(value if value is not None else "")
        return

    print(json.dumps(status, indent=2))


def cmd_get_session(args) -> None:
    """Get a specific session or a field from it."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    sessions = data.get("sessions", [])
    session = None

    # Find the session
    if args.session_id == -1 and sessions:
        session = sessions[-1]
    else:
        for s in sessions:
            if s.get("session_id") == args.session_id:
                session = s
                break

    if session is None:
        print(f"ERROR: Session {args.session_id} not found", file=sys.stderr)
        sys.exit(1)

    # If a specific field is requested, return just that value
    if args.field:
        field = args.field
        # Handle nested fields like "commit_range.from"
        if "." in field:
            parts = field.split(".")
            value = session
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
        else:
            value = session.get(field)

        if value is None:
            print("")
        elif isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2))
        else:
            print(value)
        return

    print(json.dumps(session, indent=2))


def cmd_get_review_type(args) -> None:
    """Determine the type of review needed based on current branch."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    status = data["status"]
    branch = status.get("current_branch", "")
    feature_id = status.get("current_feature")

    if branch and branch.startswith("refactor/"):
        print("REVIEW_TYPE: ARCHITECTURE_REFACTOR")
        print(f"BRANCH: {branch}")
    else:
        print(f"REVIEW_TYPE: FEATURE")
        print(f"FEATURE_ID: {feature_id}")
        print(f"BRANCH: {branch}")


def cmd_next_session_id(args) -> None:
    """Get the next session ID (current count + 1)."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    sessions = data.get("sessions", [])
    next_id = max([s.get("session_id", 0) for s in sessions], default=0) + 1
    print(next_id)


def cmd_list(args) -> None:
    """List all sessions."""
    data = load_progress(args.file)
    if data is None:
        print(f"ERROR: {args.file} does not exist.", file=sys.stderr)
        sys.exit(1)

    for session in data.get("sessions", []):
        sid = session.get("session_id")
        agent = session.get("agent_type")
        outcome = session.get("outcome")
        summary = session.get("summary", "")[:50]
        print(f"[{sid}] {agent}: {outcome} - {summary}...")


def main():
    parser = argparse.ArgumentParser(
        description="Progress log manager - MANDATORY for all progress operations"
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        default=None,
        help="Path to progress.json (overrides --agent-state-dir)"
    )
    parser.add_argument(
        "--agent-state-dir", "-d",
        type=Path,
        default=None,
        help="Agent state directory (progress.json will be in this dir)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize progress.json")
    init_parser.add_argument("--project-name", "-n", required=True, help="Project name")
    init_parser.add_argument("--feature-count", "-c", type=int, required=True, help="Total features")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing file")

    # add-session
    add_parser = subparsers.add_parser("add-session", help="Add session entry")
    add_parser.add_argument("--agent-type", "-a", required=True,
                           choices=["INITIALIZER", "BROWNFIELD_INITIALIZER", "IMPLEMENT", "BUGFIX", "REVIEW", "FIX", "ARCHITECTURE", "GLOBAL_FIX"],
                           help="Agent type")
    add_parser.add_argument("--summary", "-s", required=True, help="Session summary")
    add_parser.add_argument("--outcome", "-o", required=True,
                           choices=["SUCCESS", "READY_FOR_REVIEW", "APPROVED", "REQUEST_CHANGES",
                                   "PASS_WITH_COMMENTS", "REJECT", "ERROR"],
                           help="Session outcome")
    add_parser.add_argument("--features", help="Comma-separated feature IDs touched")
    add_parser.add_argument("--commits", nargs="*", help="Commits in format 'hash:message'")
    add_parser.add_argument("--commit-from", help="Starting commit of range")
    add_parser.add_argument("--commit-to", help="Ending commit of range")
    add_parser.add_argument("--started-at", help="Session start time (ISO 8601)")
    add_parser.add_argument("--next-phase", choices=["IMPLEMENT", "REVIEW", "FIX", "ARCHITECTURE", "GLOBAL_FIX"],
                           help="Set next phase")
    add_parser.add_argument("--current-feature", help="Set current feature (use 'null' to clear)")
    add_parser.add_argument("--current-branch", help="Set current branch (use 'null' to clear)")

    # update-status
    status_parser = subparsers.add_parser("update-status", help="Update status")
    status_parser.add_argument("--phase", choices=["IMPLEMENT", "REVIEW", "FIX", "ARCHITECTURE", "GLOBAL_FIX"])
    status_parser.add_argument("--feature", help="Current feature (use 'null' to clear)")
    status_parser.add_argument("--branch", help="Current branch (use 'null' to clear)")
    status_parser.add_argument("--features-completed", type=int)
    status_parser.add_argument("--features-passing", type=int)

    # get-status
    get_status_parser = subparsers.add_parser("get-status", help="Get current status")
    get_status_parser.add_argument("--field", help="Get specific field value (current_branch, current_feature, current_phase, etc.)")

    # get-session
    get_session_parser = subparsers.add_parser("get-session", help="Get session by ID")
    get_session_parser.add_argument("session_id", type=int, help="Session ID (-1 for last)")
    get_session_parser.add_argument("--field", help="Get specific field (e.g., agent_type, commit_range.from)")

    # get-review-type
    subparsers.add_parser("get-review-type", help="Determine review type (FEATURE or ARCHITECTURE_REFACTOR)")

    # next-session-id
    subparsers.add_parser("next-session-id", help="Get the next session ID")

    # list
    subparsers.add_parser("list", help="List all sessions")

    args = parser.parse_args()

    # Resolve file path: --file > --agent-state-dir > AGENT_STATE_DIR env > current dir
    import os
    if args.file is not None:
        pass  # Use explicit file path
    elif args.agent_state_dir is not None:
        args.file = args.agent_state_dir / "progress.json"
    elif os.environ.get("AGENT_STATE_DIR"):
        args.file = Path(os.environ["AGENT_STATE_DIR"]) / "progress.json"
    else:
        args.file = Path("progress.json")  # Default to current directory

    commands = {
        "init": cmd_init,
        "add-session": cmd_add_session,
        "update-status": cmd_update_status,
        "get-status": cmd_get_status,
        "get-session": cmd_get_session,
        "get-review-type": cmd_get_review_type,
        "next-session-id": cmd_next_session_id,
        "list": cmd_list,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
