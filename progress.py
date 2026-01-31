"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
"""

import json
from pathlib import Path
from typing import Optional


def count_passing_features(state_dir: Path) -> tuple[int, int]:
    """
    Count passing and total features in feature_list.json.

    Handles both flat array format and nested {features: [...]} format.

    Args:
        state_dir: Agent state directory containing feature_list.json

    Returns:
        (passing_count, total_count)
    """
    tests_file = state_dir / "feature_list.json"

    if not tests_file.exists():
        return 0, 0

    try:
        with open(tests_file, "r") as f:
            data = json.load(f)

        # Handle nested format: {"features": [...]}
        if isinstance(data, dict) and "features" in data:
            features = data["features"]
        elif isinstance(data, list):
            features = data
        else:
            return 0, 0

        total = len(features)
        passing = sum(1 for f in features if f.get("passes", False))

        return passing, total
    except (json.JSONDecodeError, IOError):
        return 0, 0


def get_next_feature(state_dir: Path) -> Optional[dict]:
    """
    Get the next unimplemented feature from feature_list.json.

    Args:
        state_dir: Agent state directory containing feature_list.json

    Returns:
        The next feature dict or None if all complete
    """
    tests_file = state_dir / "feature_list.json"

    if not tests_file.exists():
        return None

    try:
        with open(tests_file, "r") as f:
            data = json.load(f)

        # Handle nested format
        if isinstance(data, dict) and "features" in data:
            features = data["features"]
        elif isinstance(data, list):
            features = data
        else:
            return None

        # Find first feature that doesn't pass
        for feature in features:
            if not feature.get("passes", False):
                return feature

        return None
    except (json.JSONDecodeError, IOError):
        return None


def print_session_header(
    session_num: int,
    session_type: str,
    model: str = None,
    feature: str = None,
    branch: str = None,
) -> None:
    """Print a formatted header for the session."""
    print("\n" + "=" * 70)
    header = f"  SESSION {session_num}: {session_type}"
    if model:
        header += f" ({model})"
    print(header)
    if feature:
        print(f"  Feature: {feature}")
    if branch:
        print(f"  Branch: {branch}")
    print("=" * 70)
    print()


def print_progress_summary(state_dir: Path) -> None:
    """Print a summary of current progress."""
    passing, total = count_passing_features(state_dir)

    if total > 0:
        percentage = (passing / total) * 100
        bar_width = 40
        filled = int(bar_width * passing / total)
        bar = "█" * filled + "░" * (bar_width - filled)
        print(f"\nProgress: [{bar}] {passing}/{total} features ({percentage:.1f}%)")
    else:
        print("\nProgress: feature_list.json not yet created")


