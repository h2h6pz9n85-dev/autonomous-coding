"""
Tests for Brownfield Initialization (Part 1)
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from config import (
    AgentConfig,
    SessionState,
    SessionType,
    detect_existing_project,
    get_model_for_session,
    get_next_session_type,
    get_next_work_session,
)


class TestDetectExistingProject:
    """Tests for detect_existing_project function."""

    def test_empty_directory_returns_false(self, tmp_path):
        assert detect_existing_project(tmp_path) is False

    def test_feature_list_only_returns_false(self, tmp_path):
        (tmp_path / "feature_list.json").write_text("{}")
        assert detect_existing_project(tmp_path) is False

    def test_progress_only_returns_false(self, tmp_path):
        (tmp_path / "progress.json").write_text("{}")
        assert detect_existing_project(tmp_path) is False

    def test_both_files_returns_true(self, tmp_path):
        (tmp_path / "feature_list.json").write_text("{}")
        (tmp_path / "progress.json").write_text("{}")
        assert detect_existing_project(tmp_path) is True


class TestBrownfieldConfig:
    """Tests for brownfield-related config fields."""

    def test_config_has_brownfield_fields(self):
        config = AgentConfig(project_dir=Path("/tmp/test"))
        assert config.input_file is None
        assert config.brownfield_model == "opus"

    def test_config_accepts_input_file(self, tmp_path):
        input_file = tmp_path / "input.txt"
        input_file.write_text("test")
        config = AgentConfig(project_dir=tmp_path, input_file=input_file)
        assert config.input_file == input_file

    def test_config_serialization_includes_brownfield_fields(self, tmp_path):
        config = AgentConfig(
            project_dir=tmp_path,
            input_file=tmp_path / "input.txt",
            brownfield_model="sonnet",
        )
        data = config.to_dict()
        assert "input_file" in data
        assert "brownfield_model" in data
        assert data["brownfield_model"] == "sonnet"


class TestBrownfieldSessionType:
    """Tests for BROWNFIELD_INITIALIZER session type."""

    def test_session_type_exists(self):
        assert SessionType.BROWNFIELD_INITIALIZER == "BROWNFIELD_INITIALIZER"

    def test_brownfield_initializer_to_implement(self):
        state = SessionState(session_type=SessionType.BROWNFIELD_INITIALIZER)
        config = AgentConfig(project_dir=Path("/tmp"))
        next_type = get_next_session_type(state, config)
        assert next_type == SessionType.IMPLEMENT

    def test_brownfield_uses_brownfield_model(self):
        config = AgentConfig(project_dir=Path("/tmp"), brownfield_model="opus")
        model = get_model_for_session(SessionType.BROWNFIELD_INITIALIZER, config)
        assert model == "opus"


class TestFeaturesScriptCommands:
    """Tests for new features.py commands (next-id, append)."""

    @pytest.fixture
    def feature_list_file(self, tmp_path):
        """Create a test feature_list.json."""
        data = {
            "total_features": 3,
            "features": [
                {"id": "FEAT-001", "name": "Feature 1", "passes": True},
                {"id": "FEAT-002", "name": "Feature 2", "passes": False},
                {"id": "BUG-001", "name": "Bug 1", "type": "bug", "passes": False},
            ],
        }
        path = tmp_path / "feature_list.json"
        path.write_text(json.dumps(data))
        return path

    def test_next_id_feat(self, feature_list_file):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(feature_list_file), "next-id", "--type", "FEAT"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "FEAT-003"

    def test_next_id_bug(self, feature_list_file):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(feature_list_file), "next-id", "--type", "BUG"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "BUG-002"

    def test_append_entries(self, feature_list_file):
        entries = json.dumps([
            {"id": "FEAT-003", "name": "New Feature", "passes": False},
            {"id": "BUG-002", "name": "New Bug", "type": "bug", "passes": False},
        ])
        result = subprocess.run(
            [
                "python3", "scripts/features.py", "-f", str(feature_list_file),
                "append", "--entries", entries, "--source-appspec", "app_spec_002.txt"
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "SUCCESS" in result.stdout
        assert "FEAT-003" in result.stdout
        assert "BUG-002" in result.stdout

        # Verify entries were added
        with open(feature_list_file) as f:
            data = json.load(f)
        assert len(data["features"]) == 5
        assert data["features"][-1]["source_appspec"] == "app_spec_002.txt"

    def test_stats_shows_bug_count(self, feature_list_file):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(feature_list_file), "stats"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Bugs: 0/1 resolved" in result.stdout
        assert "Features: 1/2 passing" in result.stdout
        assert "Next: BUG-001 (bug - priority)" in result.stdout


# ============================================================================
# Part 2: Bugfix Agent Tests
# ============================================================================


class TestBugfixConfig:
    """Tests for bugfix-related config fields."""

    def test_config_has_bugfix_model(self):
        config = AgentConfig(project_dir=Path("/tmp/test"))
        assert config.bugfix_model == "sonnet"

    def test_config_serialization_includes_bugfix_model(self, tmp_path):
        config = AgentConfig(project_dir=tmp_path, bugfix_model="opus")
        data = config.to_dict()
        assert "bugfix_model" in data
        assert data["bugfix_model"] == "opus"


class TestBugfixSessionType:
    """Tests for BUGFIX session type."""

    def test_session_type_exists(self):
        assert SessionType.BUGFIX == "BUGFIX"

    def test_bugfix_to_review(self):
        state = SessionState(session_type=SessionType.BUGFIX)
        config = AgentConfig(project_dir=Path("/tmp"))
        next_type = get_next_session_type(state, config)
        assert next_type == SessionType.REVIEW

    def test_bugfix_uses_bugfix_model(self):
        config = AgentConfig(project_dir=Path("/tmp"), bugfix_model="opus")
        model = get_model_for_session(SessionType.BUGFIX, config)
        assert model == "opus"


class TestOrchestratorAgentSelection:
    """Tests for orchestrator-driven BUGFIX vs IMPLEMENT selection."""

    def test_returns_bugfix_when_pending_bugs(self, tmp_path):
        data = {
            "features": [
                {"id": "FEAT-001", "name": "Feature", "passes": False},
                {"id": "BUG-001", "name": "Bug", "type": "bug", "passes": False},
            ]
        }
        (tmp_path / "feature_list.json").write_text(json.dumps(data))
        assert get_next_work_session(tmp_path) == SessionType.BUGFIX

    def test_returns_implement_when_no_bugs(self, tmp_path):
        data = {
            "features": [
                {"id": "FEAT-001", "name": "Feature", "passes": False},
                {"id": "BUG-001", "name": "Bug", "type": "bug", "passes": True},
            ]
        }
        (tmp_path / "feature_list.json").write_text(json.dumps(data))
        assert get_next_work_session(tmp_path) == SessionType.IMPLEMENT

    def test_returns_none_when_all_done(self, tmp_path):
        data = {
            "features": [
                {"id": "FEAT-001", "name": "Feature", "passes": True},
                {"id": "BUG-001", "name": "Bug", "type": "bug", "passes": True},
            ]
        }
        (tmp_path / "feature_list.json").write_text(json.dumps(data))
        assert get_next_work_session(tmp_path) is None

    def test_returns_implement_when_no_feature_list(self, tmp_path):
        # No feature_list.json exists
        assert get_next_work_session(tmp_path) == SessionType.IMPLEMENT


class TestFeaturesListCommand:
    """Tests for the updated list command with priority sections."""

    @pytest.fixture
    def mixed_feature_list(self, tmp_path):
        data = {
            "features": [
                {"id": "FEAT-001", "name": "Feature 1", "passes": True},
                {"id": "FEAT-002", "name": "Feature 2", "passes": False},
                {"id": "BUG-001", "name": "Bug 1", "type": "bug", "passes": False},
                {"id": "BUG-002", "name": "Bug 2", "type": "bug", "passes": True},
            ]
        }
        path = tmp_path / "feature_list.json"
        path.write_text(json.dumps(data))
        return path

    def test_list_shows_bugs_section(self, mixed_feature_list):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(mixed_feature_list), "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "=== BUGS (priority) ===" in result.stdout
        assert "BUG-001" in result.stdout

    def test_list_shows_features_section(self, mixed_feature_list):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(mixed_feature_list), "list"],
            capture_output=True,
            text=True,
        )
        assert "=== FEATURES ===" in result.stdout
        assert "FEAT-002" in result.stdout

    def test_list_shows_summary(self, mixed_feature_list):
        result = subprocess.run(
            ["python3", "scripts/features.py", "-f", str(mixed_feature_list), "list"],
            capture_output=True,
            text=True,
        )
        assert "Summary:" in result.stdout
        assert "1 bugs pending" in result.stdout
        assert "1 features pending" in result.stdout
