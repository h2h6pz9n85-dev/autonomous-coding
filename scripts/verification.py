#!/usr/bin/env python3
"""
Verification Manager
====================

MANDATORY wrapper for verification artifact management.
Agents MUST use this CLI for all verification operations.

Commands:
    prepare       Prepare verification input for subagent
    status        Check verification status for a session
    list          List all verification reports
    report        Generate verification report template

Usage:
    python3 scripts/verification.py prepare --session-id 15 --feature-ids "F001,F002"
    python3 scripts/verification.py status --session-id 15
    python3 scripts/verification.py list
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_timestamp() -> str:
    """Get current ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def get_agent_state_dir(args) -> Path:
    """Resolve agent state directory from args or environment."""
    if hasattr(args, 'agent_state_dir') and args.agent_state_dir:
        return Path(args.agent_state_dir)
    if os.environ.get("AGENT_STATE_DIR"):
        return Path(os.environ["AGENT_STATE_DIR"])
    return Path(".agent_state")


def load_feature_list(agent_state_dir: Path) -> dict:
    """Load feature_list.json from agent state directory."""
    feature_file = agent_state_dir / "feature_list.json"
    if not feature_file.exists():
        return {"features": []}
    with open(feature_file) as f:
        return json.load(f)


def cmd_prepare(args) -> None:
    """Prepare verification input file for subagent.

    Creates the verification folder structure and input file
    that the verification subagent will use.
    """
    agent_state_dir = get_agent_state_dir(args)
    verification_dir = agent_state_dir / "verification" / str(args.session_id)

    # Create directory structure
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "screenshots").mkdir(exist_ok=True)
    (verification_dir / "test_evidence").mkdir(exist_ok=True)

    # Load feature specifications
    feature_list = load_feature_list(agent_state_dir)
    feature_ids = [f.strip() for f in args.feature_ids.split(",") if f.strip()]

    features = []
    for feature in feature_list.get("features", []):
        if feature.get("id") in feature_ids:
            features.append(feature)

    if not features and feature_ids:
        print(f"WARNING: No features found matching IDs: {feature_ids}", file=sys.stderr)

    # Determine URLs from environment or defaults
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")

    # Determine test commands from environment or defaults
    test_commands = []
    if os.environ.get("TEST_COMMANDS"):
        test_commands = os.environ["TEST_COMMANDS"].split(",")
    else:
        test_commands = ["pytest tests/", "npm run test"]

    # Create verification input
    verification_input = {
        "session_id": args.session_id,
        "feature_specifications": features,
        "feature_ids": feature_ids,
        "test_commands": test_commands,
        "app_urls": {
            "frontend": frontend_url,
            "backend": backend_url
        },
        "verification_output_dir": str(verification_dir),
        "created_at": get_timestamp(),
        "agent_type": args.agent_type if hasattr(args, 'agent_type') and args.agent_type else "IMPLEMENT"
    }

    input_file = verification_dir / "verification_input.json"
    with open(input_file, "w") as f:
        json.dump(verification_input, f, indent=2)

    print(f"SUCCESS: Verification input prepared")
    print(f"Directory: {verification_dir}")
    print(f"Input file: {input_file}")
    print(json.dumps(verification_input, indent=2))


def cmd_status(args) -> None:
    """Check verification status for a session."""
    agent_state_dir = get_agent_state_dir(args)
    verification_dir = agent_state_dir / "verification" / str(args.session_id)

    if not verification_dir.exists():
        result = {
            "session_id": args.session_id,
            "status": "NOT_STARTED",
            "message": "Verification directory does not exist"
        }
        print(json.dumps(result, indent=2))
        return

    report_file = verification_dir / "verification.md"
    input_file = verification_dir / "verification_input.json"
    screenshots_dir = verification_dir / "screenshots"

    # Check if input exists but report doesn't
    if input_file.exists() and not report_file.exists():
        result = {
            "session_id": args.session_id,
            "status": "IN_PROGRESS",
            "message": "Verification input exists, awaiting report",
            "input_file": str(input_file)
        }
        print(json.dumps(result, indent=2))
        return

    if not report_file.exists():
        result = {
            "session_id": args.session_id,
            "status": "NOT_STARTED",
            "message": "No verification report found"
        }
        print(json.dumps(result, indent=2))
        return

    # Parse verification.md for status
    content = report_file.read_text()

    if "**Status:** VERIFIED" in content:
        status = "VERIFIED"
    elif "**Status:** NOT_VERIFIED" in content:
        status = "NOT_VERIFIED"
    elif "**Status:** INCOMPLETE" in content:
        status = "INCOMPLETE"
    else:
        status = "UNKNOWN"

    # Count screenshots
    screenshots = list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []

    # Check for test evidence
    test_evidence_dir = verification_dir / "test_evidence"
    test_output_exists = (test_evidence_dir / "test_output.txt").exists() if test_evidence_dir.exists() else False

    result = {
        "session_id": args.session_id,
        "status": status,
        "report_path": str(report_file),
        "screenshots_count": len(screenshots),
        "test_evidence_exists": test_output_exists,
        "verification_dir": str(verification_dir)
    }

    print(json.dumps(result, indent=2))


def cmd_list(args) -> None:
    """List all verification reports."""
    agent_state_dir = get_agent_state_dir(args)
    verification_base = agent_state_dir / "verification"

    if not verification_base.exists():
        print("No verification reports found.")
        return

    reports = []
    for session_dir in sorted(verification_base.iterdir()):
        if not session_dir.is_dir():
            continue

        try:
            session_id = int(session_dir.name)
        except ValueError:
            continue

        report_file = session_dir / "verification.md"
        screenshots_dir = session_dir / "screenshots"

        status = "NOT_STARTED"
        if report_file.exists():
            content = report_file.read_text()
            if "**Status:** VERIFIED" in content:
                status = "VERIFIED"
            elif "**Status:** NOT_VERIFIED" in content:
                status = "NOT_VERIFIED"
            elif "**Status:** INCOMPLETE" in content:
                status = "INCOMPLETE"
            else:
                status = "IN_PROGRESS"
        elif (session_dir / "verification_input.json").exists():
            status = "IN_PROGRESS"

        screenshots_count = len(list(screenshots_dir.glob("*.png"))) if screenshots_dir.exists() else 0

        reports.append({
            "session_id": session_id,
            "status": status,
            "screenshots": screenshots_count
        })

    if not reports:
        print("No verification reports found.")
        return

    # Print summary
    print(f"{'Session':<10} {'Status':<15} {'Screenshots':<12}")
    print("-" * 37)
    for r in reports:
        print(f"{r['session_id']:<10} {r['status']:<15} {r['screenshots']:<12}")

    # Print stats
    verified = sum(1 for r in reports if r['status'] == 'VERIFIED')
    not_verified = sum(1 for r in reports if r['status'] == 'NOT_VERIFIED')
    in_progress = sum(1 for r in reports if r['status'] == 'IN_PROGRESS')

    print("-" * 37)
    print(f"Total: {len(reports)} | Verified: {verified} | Not Verified: {not_verified} | In Progress: {in_progress}")


def cmd_report(args) -> None:
    """Generate a verification report template for manual completion.

    Used when the subagent cannot complete verification and the coder
    must complete it manually.
    """
    agent_state_dir = get_agent_state_dir(args)
    verification_dir = agent_state_dir / "verification" / str(args.session_id)

    if not verification_dir.exists():
        print(f"ERROR: Verification directory does not exist: {verification_dir}", file=sys.stderr)
        print("Run 'prepare' first to create the directory structure.", file=sys.stderr)
        sys.exit(1)

    input_file = verification_dir / "verification_input.json"
    if not input_file.exists():
        print(f"ERROR: Verification input not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    with open(input_file) as f:
        verification_input = json.load(f)

    # Generate report template
    agent_type = verification_input.get("agent_type", "IMPLEMENT")
    feature_ids = verification_input.get("feature_ids", [])
    features = verification_input.get("feature_specifications", [])

    template = f"""# Verification Report: Session {args.session_id}

## Metadata
- **Session ID:** {args.session_id}
- **Agent Type:** {agent_type}
- **Timestamp:** {get_timestamp()}
- **Verified By:** [Manual / Verification Subagent]

## Features Verified
| Feature ID | Name | Specification Summary |
|------------|------|----------------------|
"""

    for feature in features:
        fid = feature.get("id", "N/A")
        name = feature.get("name", "N/A")
        desc = feature.get("description", "N/A")[:50]
        template += f"| {fid} | {name} | {desc}... |\n"

    if not features:
        for fid in feature_ids:
            template += f"| {fid} | [Name] | [Description] |\n"

    template += """
---

## Test Evidence

### Tests Created
| Test Name | Purpose | What It Verifies |
|-----------|---------|------------------|
| [test_name] | [purpose] | [what it verifies] |

### Test Execution
- **Command:** [pytest command]
- **Exit Code:** [0 or error code]
- **Result:** [X passed, Y failed]
- **Raw Output:** See `test_evidence/test_output.txt`

---

## Visual Evidence

### Screenshot: 001-[description].png
- **URL:** [URL tested]
- **What This Shows:** [Description]
- **Expected Per Spec:** [Expected behavior]
- **Match:** [YES / NO]

---

## Specification Compliance Checklist

| Requirement | Evidence | Status |
|-------------|----------|--------|
| [requirement from spec] | [screenshot/test] | [VERIFIED / NOT_VERIFIED] |

---

## Verification Conclusion

**Status:** [VERIFIED / NOT_VERIFIED / INCOMPLETE]
**Reason:** [Explanation]

---

## Limitations Noted

- [What was not tested and why]
"""

    report_file = verification_dir / "verification.md"
    with open(report_file, "w") as f:
        f.write(template)

    print(f"SUCCESS: Report template generated: {report_file}")
    print("Edit this file to complete verification manually.")


def main():
    parser = argparse.ArgumentParser(
        description="Verification manager - MANDATORY for verification operations"
    )
    parser.add_argument(
        "--agent-state-dir", "-d",
        type=Path,
        default=None,
        help="Agent state directory (default: AGENT_STATE_DIR env or .agent_state)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # prepare
    prepare_parser = subparsers.add_parser("prepare", help="Prepare verification input")
    prepare_parser.add_argument("--session-id", "-s", type=int, required=True,
                                help="Session ID for this verification")
    prepare_parser.add_argument("--feature-ids", "-f", required=True,
                                help="Comma-separated feature IDs to verify")
    prepare_parser.add_argument("--agent-type", "-a", default="IMPLEMENT",
                                choices=["IMPLEMENT", "FIX", "BUGFIX", "GLOBAL_FIX"],
                                help="Type of agent that performed the implementation")

    # status
    status_parser = subparsers.add_parser("status", help="Check verification status")
    status_parser.add_argument("--session-id", "-s", type=int, required=True,
                               help="Session ID to check")

    # list
    subparsers.add_parser("list", help="List all verification reports")

    # report
    report_parser = subparsers.add_parser("report", help="Generate report template")
    report_parser.add_argument("--session-id", "-s", type=int, required=True,
                               help="Session ID for this report")

    args = parser.parse_args()

    commands = {
        "prepare": cmd_prepare,
        "status": cmd_status,
        "list": cmd_list,
        "report": cmd_report,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
