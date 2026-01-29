"""
Tests for Multi-Agent Flow
==========================

Verifies the state machine transitions between agents work correctly.
Mocks Claude Code CLI outputs to simulate agent responses.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import tempfile
import shutil

from config import AgentConfig, SessionState, SessionType, get_next_session_type, get_model_for_session


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def base_config(temp_project_dir):
    """Create a basic AgentConfig for testing."""
    spec_file = temp_project_dir / "app_spec.txt"
    spec_file.write_text("<app_specification><name>Test App</name></app_specification>")

    return AgentConfig(
        project_dir=temp_project_dir,
        spec_file=spec_file,
        implement_model="sonnet",
        review_model="opus",
        fix_model="sonnet",
        architecture_model="opus",
        architecture_interval=5,
        feature_count=10,
        main_branch="main",
    )


@pytest.fixture
def feature_list_data():
    """Sample feature list with 3 features."""
    return {
        "project_name": "Test App",
        "total_features": 3,
        "features": [
            {"id": "F001", "name": "Health Check", "passes": False},
            {"id": "F002", "name": "User Login", "passes": False},
            {"id": "F003", "name": "Dashboard", "passes": False},
        ]
    }


@pytest.fixture
def progress_data():
    """Sample progress.json structure."""
    return {
        "project": {
            "name": "Test App",
            "created_at": "2025-01-29T10:00:00Z",
            "total_features": 3
        },
        "status": {
            "updated_at": "2025-01-29T10:00:00Z",
            "features_completed": 0,
            "features_passing": 0,
            "current_phase": "IMPLEMENT",
            "current_feature": None,
            "current_branch": None,
            "head_commit": "abc1234"
        },
        "sessions": []
    }


# -----------------------------------------------------------------------------
# State Machine Tests
# -----------------------------------------------------------------------------

class TestGetNextSessionType:
    """Test the state machine that determines next agent type."""

    def test_initializer_to_implement(self, base_config):
        """After INITIALIZER, next session should be IMPLEMENT."""
        state = SessionState(session_type=SessionType.INITIALIZER)

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.IMPLEMENT

    def test_implement_to_review(self, base_config):
        """After IMPLEMENT, next session should be REVIEW."""
        state = SessionState(session_type=SessionType.IMPLEMENT)

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.REVIEW

    def test_review_pass_to_implement(self, base_config):
        """After REVIEW with no issues, next session should be IMPLEMENT."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],  # No issues = PASS
            features_completed=1,
        )

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.IMPLEMENT

    def test_review_with_issues_to_fix(self, base_config):
        """After REVIEW with issues, next session should be FIX."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=["Missing error handling"],
        )

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.FIX

    def test_fix_to_review(self, base_config):
        """After FIX, next session should be REVIEW (re-verification)."""
        state = SessionState(session_type=SessionType.FIX)

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.REVIEW

    def test_architecture_to_implement(self, base_config):
        """After ARCHITECTURE review, next session should be IMPLEMENT."""
        state = SessionState(session_type=SessionType.ARCHITECTURE)

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.IMPLEMENT

    def test_architecture_triggered_at_interval(self, base_config):
        """Architecture review triggers every N features."""
        base_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],  # PASS
            features_completed=5,  # Exactly at interval
        )

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.ARCHITECTURE

    def test_architecture_not_triggered_before_interval(self, base_config):
        """Architecture review does NOT trigger before interval."""
        base_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=3,  # Before interval
        )

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.IMPLEMENT

    def test_architecture_triggered_at_multiples(self, base_config):
        """Architecture review triggers at multiples of interval."""
        base_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=10,  # 2x interval
        )

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.ARCHITECTURE


class TestGetModelForSession:
    """Test model selection for each session type."""

    def test_implement_uses_implement_model(self, base_config):
        model = get_model_for_session(SessionType.IMPLEMENT, base_config)
        assert model == base_config.implement_model

    def test_review_uses_review_model(self, base_config):
        model = get_model_for_session(SessionType.REVIEW, base_config)
        assert model == base_config.review_model

    def test_fix_uses_fix_model(self, base_config):
        model = get_model_for_session(SessionType.FIX, base_config)
        assert model == base_config.fix_model

    def test_architecture_uses_architecture_model(self, base_config):
        model = get_model_for_session(SessionType.ARCHITECTURE, base_config)
        assert model == base_config.architecture_model

    def test_initializer_uses_implement_model(self, base_config):
        """INITIALIZER uses the implement model."""
        model = get_model_for_session(SessionType.INITIALIZER, base_config)
        assert model == base_config.implement_model


# -----------------------------------------------------------------------------
# Session State Persistence Tests
# -----------------------------------------------------------------------------

class TestSessionStatePersistence:
    """Test saving and loading session state."""

    def test_save_and_load_state(self, temp_project_dir):
        """State should round-trip through save/load."""
        original = SessionState(
            iteration=5,
            features_completed=2,
            current_feature="F003",
            current_branch="feature/dashboard",
            session_type=SessionType.FIX,
            review_issues=["Issue 1", "Issue 2"],
        )

        original.save(temp_project_dir)
        loaded = SessionState.load(temp_project_dir)

        assert loaded.iteration == original.iteration
        assert loaded.features_completed == original.features_completed
        assert loaded.current_feature == original.current_feature
        assert loaded.current_branch == original.current_branch
        assert loaded.session_type == original.session_type
        assert loaded.review_issues == original.review_issues

    def test_load_missing_state_returns_default(self, temp_project_dir):
        """Loading from empty directory returns default state."""
        state = SessionState.load(temp_project_dir)

        assert state.iteration == 0
        assert state.features_completed == 0
        assert state.session_type == SessionType.INITIALIZER


# -----------------------------------------------------------------------------
# Config Persistence Tests
# -----------------------------------------------------------------------------

class TestAgentConfigPersistence:
    """Test saving and loading agent config."""

    def test_save_and_load_config(self, base_config, temp_project_dir):
        """Config should round-trip through save/load."""
        config_path = temp_project_dir / "config.json"

        base_config.save(config_path)
        loaded = AgentConfig.load(config_path)

        assert loaded.project_dir == base_config.project_dir
        assert loaded.implement_model == base_config.implement_model
        assert loaded.review_model == base_config.review_model
        assert loaded.architecture_interval == base_config.architecture_interval


# -----------------------------------------------------------------------------
# Integration Flow Tests (Mocked Claude Code)
# -----------------------------------------------------------------------------

class TestFullFlowWithMockedAgent:
    """
    Test complete agent flow by mocking Claude Code CLI responses.

    These tests simulate the orchestrator running through various scenarios.
    """

    @pytest.fixture
    def setup_project_files(self, temp_project_dir, feature_list_data, progress_data):
        """Set up initial project files."""
        # Write feature_list.json
        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(feature_list_data, indent=2)
        )

        # Write progress.json
        (temp_project_dir / "progress.json").write_text(
            json.dumps(progress_data, indent=2)
        )

        # Write reviews.json
        (temp_project_dir / "reviews.json").write_text(
            json.dumps({"schema_version": "1.0", "reviews": [], "fixes": []}, indent=2)
        )

        return temp_project_dir

    def test_happy_path_implement_review_pass(self, base_config, setup_project_files):
        """
        Test: IMPLEMENT → REVIEW (PASS) → next IMPLEMENT

        Simulates a feature being implemented and passing review on first try.
        """
        state = SessionState(
            session_type=SessionType.IMPLEMENT,
            current_feature="F001",
            current_branch="feature/health-check",
        )

        # After IMPLEMENT, should go to REVIEW
        next_type = get_next_session_type(state, base_config)
        assert next_type == SessionType.REVIEW

        # Simulate REVIEW passing (no issues)
        state.session_type = SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 1

        # After PASS, should go to IMPLEMENT (next feature)
        next_type = get_next_session_type(state, base_config)
        assert next_type == SessionType.IMPLEMENT

    def test_implement_review_fix_review_pass(self, base_config, setup_project_files):
        """
        Test: IMPLEMENT → REVIEW (REQUEST_CHANGES) → FIX → REVIEW (PASS)

        Simulates a feature failing review, getting fixed, then passing.
        """
        state = SessionState(
            session_type=SessionType.IMPLEMENT,
            current_feature="F001",
        )

        # IMPLEMENT → REVIEW
        assert get_next_session_type(state, base_config) == SessionType.REVIEW

        # REVIEW finds issues → FIX
        state.session_type = SessionType.REVIEW
        state.review_issues = ["Missing tests"]
        assert get_next_session_type(state, base_config) == SessionType.FIX

        # FIX → REVIEW (re-verification)
        state.session_type = SessionType.FIX
        assert get_next_session_type(state, base_config) == SessionType.REVIEW

        # REVIEW passes → IMPLEMENT
        state.session_type = SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 1
        assert get_next_session_type(state, base_config) == SessionType.IMPLEMENT

    def test_multiple_fix_cycles(self, base_config, setup_project_files):
        """
        Test: Multiple FIX → REVIEW cycles before passing.

        Simulates a feature requiring multiple fix attempts.
        """
        state = SessionState(
            session_type=SessionType.REVIEW,
            current_feature="F001",
            review_issues=["Issue 1"],
        )

        # First cycle: REVIEW → FIX → REVIEW
        assert get_next_session_type(state, base_config) == SessionType.FIX
        state.session_type = SessionType.FIX
        assert get_next_session_type(state, base_config) == SessionType.REVIEW

        # Still has issues
        state.session_type = SessionType.REVIEW
        state.review_issues = ["Issue 2"]

        # Second cycle: REVIEW → FIX → REVIEW
        assert get_next_session_type(state, base_config) == SessionType.FIX
        state.session_type = SessionType.FIX
        assert get_next_session_type(state, base_config) == SessionType.REVIEW

        # Finally passes
        state.session_type = SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 1
        assert get_next_session_type(state, base_config) == SessionType.IMPLEMENT

    def test_architecture_review_in_flow(self, base_config, setup_project_files):
        """
        Test: Architecture review triggers at interval.

        Flow: ... → REVIEW (PASS, feature 5) → ARCHITECTURE → IMPLEMENT
        """
        base_config.architecture_interval = 5

        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=5,
        )

        # At interval, should go to ARCHITECTURE
        assert get_next_session_type(state, base_config) == SessionType.ARCHITECTURE

        # After ARCHITECTURE, back to IMPLEMENT
        state.session_type = SessionType.ARCHITECTURE
        assert get_next_session_type(state, base_config) == SessionType.IMPLEMENT

    def test_full_project_lifecycle(self, base_config, setup_project_files):
        """
        Test complete project lifecycle with 3 features.

        Simulates: INIT → (IMPLEMENT → REVIEW)×3 with one fix cycle.
        """
        base_config.architecture_interval = 10  # Won't trigger for 3 features

        # Start with INITIALIZER
        state = SessionState(session_type=SessionType.INITIALIZER)

        # INITIALIZER → IMPLEMENT
        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.IMPLEMENT

        # Feature 1: IMPLEMENT → REVIEW (PASS)
        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 1

        # Feature 2: IMPLEMENT → REVIEW (REQUEST_CHANGES) → FIX → REVIEW (PASS)
        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.IMPLEMENT

        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.REVIEW
        state.review_issues = ["Bug found"]

        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.FIX

        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 2

        # Feature 3: IMPLEMENT → REVIEW (PASS)
        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.IMPLEMENT

        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.REVIEW
        state.review_issues = []
        state.features_completed = 3

        # After all features, would continue to IMPLEMENT (for more features)
        state.session_type = get_next_session_type(state, base_config)
        assert state.session_type == SessionType.IMPLEMENT


# -----------------------------------------------------------------------------
# Agent Session Mock Tests
# -----------------------------------------------------------------------------

class TestAgentSessionMocking:
    """Test agent sessions with mocked subprocess calls."""

    @pytest.mark.asyncio
    async def test_mocked_agent_session_success(self, base_config):
        """Test that agent session returns expected values on success."""
        from agent import run_agent_session

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.stdout.read = AsyncMock(side_effect=[
            b"Agent output here...",
            b"",  # EOF
        ])
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock()

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            status, response = await run_agent_session(
                prompt="Test prompt",
                project_dir=base_config.project_dir,
                model="sonnet",
                config=base_config,
            )

        assert status == "continue"
        assert "Agent output" in response

    @pytest.mark.asyncio
    async def test_mocked_agent_session_error(self, base_config):
        """Test that agent session handles errors correctly."""
        from agent import run_agent_session

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.stdout.read = AsyncMock(side_effect=[b"", b""])
        mock_process.stderr.read = AsyncMock(return_value=b"Error occurred")
        mock_process.wait = AsyncMock()

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            status, response = await run_agent_session(
                prompt="Test prompt",
                project_dir=base_config.project_dir,
                model="sonnet",
                config=base_config,
            )

        assert status == "error"


# -----------------------------------------------------------------------------
# Progress Tracking Tests
# -----------------------------------------------------------------------------

class TestProgressTracking:
    """Test progress tracking utilities."""

    def test_count_passing_features_empty(self, temp_project_dir):
        """No feature_list.json returns (0, 0)."""
        from progress import count_passing_features

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_count_passing_features_none_passing(self, temp_project_dir, feature_list_data):
        """All features failing returns correct count."""
        from progress import count_passing_features

        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(feature_list_data)
        )

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 3

    def test_count_passing_features_some_passing(self, temp_project_dir, feature_list_data):
        """Some features passing returns correct count."""
        from progress import count_passing_features

        feature_list_data["features"][0]["passes"] = True
        feature_list_data["features"][2]["passes"] = True
        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(feature_list_data)
        )

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 2
        assert total == 3

    def test_get_next_feature(self, temp_project_dir, feature_list_data):
        """Get next unimplemented feature."""
        from progress import get_next_feature

        feature_list_data["features"][0]["passes"] = True
        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(feature_list_data)
        )

        next_feature = get_next_feature(temp_project_dir)

        assert next_feature is not None
        assert next_feature["id"] == "F002"

    def test_get_next_feature_all_done(self, temp_project_dir, feature_list_data):
        """Returns None when all features pass."""
        from progress import get_next_feature

        for f in feature_list_data["features"]:
            f["passes"] = True
        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(feature_list_data)
        )

        next_feature = get_next_feature(temp_project_dir)

        assert next_feature is None


# -----------------------------------------------------------------------------
# Edge Cases
# -----------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_architecture_at_zero_features(self, base_config):
        """Architecture review should NOT trigger at 0 features."""
        base_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=0,
        )

        next_type = get_next_session_type(state, base_config)

        # Should go to IMPLEMENT, not ARCHITECTURE
        assert next_type == SessionType.IMPLEMENT

    def test_unknown_session_type_defaults_to_implement(self, base_config):
        """Unknown session type should default to IMPLEMENT."""
        state = SessionState(session_type="UNKNOWN_TYPE")

        next_type = get_next_session_type(state, base_config)

        assert next_type == SessionType.IMPLEMENT

    def test_empty_review_issues_is_pass(self, base_config):
        """Empty review_issues list means PASS."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
        )

        # Should NOT go to FIX
        next_type = get_next_session_type(state, base_config)
        assert next_type != SessionType.FIX

    def test_nested_feature_list_format(self, temp_project_dir):
        """Handle nested {features: [...]} format."""
        from progress import count_passing_features

        nested_data = {
            "features": [
                {"id": "F001", "passes": True},
                {"id": "F002", "passes": False},
            ]
        }
        (temp_project_dir / "feature_list.json").write_text(
            json.dumps(nested_data)
        )

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 1
        assert total == 2
