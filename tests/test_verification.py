"""
Verification CLI Tests
======================

Tests for scripts/verification.py CLI commands.
"""

import json
import os
import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_agent_state():
    """Create a temporary agent state directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def feature_list_file(temp_agent_state):
    """Create a feature_list.json with test features."""
    feature_list = {
        "features": [
            {
                "id": "F001",
                "name": "User Login",
                "description": "Users can log in with email/password",
                "passes": False
            },
            {
                "id": "F002",
                "name": "User Registration",
                "description": "Users can register new accounts",
                "passes": False
            },
            {
                "id": "BUG-001",
                "name": "Fix login button",
                "description": "Login button not clickable on mobile",
                "type": "bug",
                "passes": False
            }
        ]
    }
    feature_file = temp_agent_state / "feature_list.json"
    with open(feature_file, "w") as f:
        json.dump(feature_list, f, indent=2)
    return feature_file


def run_verification_cli(args, agent_state_dir=None, env=None):
    """Helper to run verification.py CLI."""
    script_path = Path(__file__).parent.parent / "scripts" / "verification.py"
    cmd = ["python3", str(script_path)]

    if agent_state_dir:
        cmd.extend(["--agent-state-dir", str(agent_state_dir)])

    cmd.extend(args)

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=run_env
    )
    return result


# -----------------------------------------------------------------------------
# Prepare Command Tests
# -----------------------------------------------------------------------------

class TestPrepareCommand:
    """Tests for the 'prepare' command."""

    def test_prepare_creates_verification_directory(self, temp_agent_state, feature_list_file):
        """prepare creates the verification directory structure."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001,F002"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        assert "SUCCESS" in result.stdout

        verification_dir = temp_agent_state / "verification" / "15"
        assert verification_dir.exists()
        assert (verification_dir / "screenshots").is_dir()
        assert (verification_dir / "test_evidence").is_dir()

    def test_prepare_creates_input_file(self, temp_agent_state, feature_list_file):
        """prepare creates verification_input.json with correct structure."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001,F002"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0

        input_file = temp_agent_state / "verification" / "15" / "verification_input.json"
        assert input_file.exists()

        with open(input_file) as f:
            data = json.load(f)

        assert data["session_id"] == 15
        assert data["feature_ids"] == ["F001", "F002"]
        assert len(data["feature_specifications"]) == 2
        assert "created_at" in data
        assert "app_urls" in data

    def test_prepare_loads_feature_specifications(self, temp_agent_state, feature_list_file):
        """prepare loads matching feature specifications from feature_list.json."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0

        input_file = temp_agent_state / "verification" / "15" / "verification_input.json"
        with open(input_file) as f:
            data = json.load(f)

        assert len(data["feature_specifications"]) == 1
        assert data["feature_specifications"][0]["id"] == "F001"
        assert data["feature_specifications"][0]["name"] == "User Login"

    def test_prepare_with_agent_type(self, temp_agent_state, feature_list_file):
        """prepare accepts agent_type parameter."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001", "--agent-type", "FIX"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0

        input_file = temp_agent_state / "verification" / "15" / "verification_input.json"
        with open(input_file) as f:
            data = json.load(f)

        assert data["agent_type"] == "FIX"

    def test_prepare_warns_on_missing_features(self, temp_agent_state, feature_list_file):
        """prepare warns when feature IDs don't exist in feature_list.json."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F999"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        assert "WARNING" in result.stderr

    def test_prepare_idempotent(self, temp_agent_state, feature_list_file):
        """prepare can be run multiple times for same session."""
        # First run
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        # Second run should succeed without error
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001,F002"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0


# -----------------------------------------------------------------------------
# Status Command Tests
# -----------------------------------------------------------------------------

class TestStatusCommand:
    """Tests for the 'status' command."""

    def test_status_not_started(self, temp_agent_state):
        """status returns NOT_STARTED when verification directory doesn't exist."""
        result = run_verification_cli(
            ["status", "--session-id", "99"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "NOT_STARTED"

    def test_status_in_progress(self, temp_agent_state, feature_list_file):
        """status returns IN_PROGRESS when input exists but no report."""
        # Prepare verification (creates input)
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        result = run_verification_cli(
            ["status", "--session-id", "15"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "IN_PROGRESS"

    def test_status_verified(self, temp_agent_state, feature_list_file):
        """status returns VERIFIED when report contains VERIFIED status."""
        # Prepare verification
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        # Create a VERIFIED report
        report_file = temp_agent_state / "verification" / "15" / "verification.md"
        report_file.write_text("""# Verification Report

**Status:** VERIFIED
**Reason:** All tests pass
""")

        result = run_verification_cli(
            ["status", "--session-id", "15"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "VERIFIED"

    def test_status_not_verified(self, temp_agent_state, feature_list_file):
        """status returns NOT_VERIFIED when report contains NOT_VERIFIED status."""
        # Prepare verification
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        # Create a NOT_VERIFIED report
        report_file = temp_agent_state / "verification" / "15" / "verification.md"
        report_file.write_text("""# Verification Report

**Status:** NOT_VERIFIED
**Reason:** Tests failed
""")

        result = run_verification_cli(
            ["status", "--session-id", "15"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "NOT_VERIFIED"

    def test_status_includes_screenshot_count(self, temp_agent_state, feature_list_file):
        """status includes count of screenshots in verification folder."""
        # Prepare verification
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            agent_state_dir=temp_agent_state
        )

        # Add some screenshots
        screenshots_dir = temp_agent_state / "verification" / "15" / "screenshots"
        (screenshots_dir / "001-test.png").write_text("fake png")
        (screenshots_dir / "002-test.png").write_text("fake png")

        # Create a report
        report_file = temp_agent_state / "verification" / "15" / "verification.md"
        report_file.write_text("**Status:** VERIFIED")

        result = run_verification_cli(
            ["status", "--session-id", "15"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["screenshots_count"] == 2


# -----------------------------------------------------------------------------
# List Command Tests
# -----------------------------------------------------------------------------

class TestListCommand:
    """Tests for the 'list' command."""

    def test_list_empty(self, temp_agent_state):
        """list shows nothing when no verifications exist."""
        result = run_verification_cli(
            ["list"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        assert "No verification reports found" in result.stdout

    def test_list_shows_verifications(self, temp_agent_state, feature_list_file):
        """list shows all verification sessions."""
        # Create multiple verification sessions
        for session_id in [10, 15, 20]:
            run_verification_cli(
                ["prepare", "--session-id", str(session_id), "--feature-ids", "F001"],
                agent_state_dir=temp_agent_state
            )

        # Add a report to one
        report_file = temp_agent_state / "verification" / "15" / "verification.md"
        report_file.write_text("**Status:** VERIFIED")

        result = run_verification_cli(
            ["list"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        assert "10" in result.stdout
        assert "15" in result.stdout
        assert "20" in result.stdout
        assert "VERIFIED" in result.stdout
        assert "IN_PROGRESS" in result.stdout


# -----------------------------------------------------------------------------
# Report Command Tests
# -----------------------------------------------------------------------------

class TestReportCommand:
    """Tests for the 'report' command."""

    def test_report_requires_prepare(self, temp_agent_state):
        """report fails if verification was not prepared first."""
        result = run_verification_cli(
            ["report", "--session-id", "99"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode != 0
        assert "ERROR" in result.stderr

    def test_report_generates_template(self, temp_agent_state, feature_list_file):
        """report generates a verification report template."""
        # Prepare verification first
        run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001,F002"],
            agent_state_dir=temp_agent_state
        )

        result = run_verification_cli(
            ["report", "--session-id", "15"],
            agent_state_dir=temp_agent_state
        )

        assert result.returncode == 0
        assert "SUCCESS" in result.stdout

        report_file = temp_agent_state / "verification" / "15" / "verification.md"
        assert report_file.exists()

        content = report_file.read_text()
        assert "Verification Report: Session 15" in content
        assert "F001" in content
        assert "F002" in content
        assert "**Status:**" in content


# -----------------------------------------------------------------------------
# Environment Variable Tests
# -----------------------------------------------------------------------------

class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_uses_agent_state_dir_env(self, temp_agent_state, feature_list_file):
        """Uses AGENT_STATE_DIR environment variable when no flag provided."""
        result = run_verification_cli(
            ["prepare", "--session-id", "15", "--feature-ids", "F001"],
            env={"AGENT_STATE_DIR": str(temp_agent_state)}
        )

        assert result.returncode == 0
        assert (temp_agent_state / "verification" / "15").exists()

    def test_flag_overrides_env(self, temp_agent_state, feature_list_file):
        """--agent-state-dir flag overrides environment variable."""
        other_dir = tempfile.mkdtemp()
        try:
            result = run_verification_cli(
                ["prepare", "--session-id", "15", "--feature-ids", "F001"],
                agent_state_dir=temp_agent_state,
                env={"AGENT_STATE_DIR": other_dir}
            )

            assert result.returncode == 0
            # Should use the flag path, not env
            assert (temp_agent_state / "verification" / "15").exists()
            assert not (Path(other_dir) / "verification" / "15").exists()
        finally:
            shutil.rmtree(other_dir)
