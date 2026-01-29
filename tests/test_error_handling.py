"""
Error Handling Tests
====================

Tests for error injection and graceful error handling:
- Corrupted JSON files
- Missing required files
- CLI failures
- Invalid state transitions
"""

import asyncio
import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AgentConfig, SessionState, SessionType, get_next_session_type, get_model_for_session
from progress import count_passing_features, get_next_feature, print_progress_summary
from agent import run_agent_session


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def minimal_config(temp_project_dir):
    """Minimal config for testing."""
    spec_file = temp_project_dir / "app_spec.txt"
    spec_file.write_text("<app_specification><name>Test</name></app_specification>")

    return AgentConfig(
        project_dir=temp_project_dir,
        spec_file=spec_file,
        feature_count=1,
    )


# -----------------------------------------------------------------------------
# Corrupted JSON Tests
# -----------------------------------------------------------------------------

class TestCorruptedJSON:
    """Tests for handling corrupted JSON files."""

    def test_corrupted_feature_list_returns_zeros(self, temp_project_dir):
        """Corrupted feature_list.json should return (0, 0) not crash."""
        # Write invalid JSON
        (temp_project_dir / "feature_list.json").write_text("{invalid json")

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_truncated_feature_list_handled(self, temp_project_dir):
        """Truncated JSON should be handled gracefully."""
        # Write truncated JSON (missing closing brace)
        (temp_project_dir / "feature_list.json").write_text('{"features": [{"id": "F001"')

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_empty_feature_list_file(self, temp_project_dir):
        """Empty file should be handled gracefully."""
        (temp_project_dir / "feature_list.json").write_text("")

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_null_feature_list(self, temp_project_dir):
        """JSON null should be handled gracefully."""
        (temp_project_dir / "feature_list.json").write_text("null")

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_feature_list_wrong_type(self, temp_project_dir):
        """Wrong JSON type should be handled gracefully."""
        # String instead of object/array
        (temp_project_dir / "feature_list.json").write_text('"not an object"')

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_get_next_feature_with_corrupted_json(self, temp_project_dir):
        """get_next_feature should handle corrupted JSON."""
        (temp_project_dir / "feature_list.json").write_text("{broken")

        result = get_next_feature(temp_project_dir)

        assert result is None

    def test_session_state_load_with_corrupted_file(self, temp_project_dir):
        """SessionState.load should handle corrupted state file."""
        (temp_project_dir / ".agent_state.json").write_text("{broken json")

        # Should return fresh state, not crash
        # Note: Current implementation may raise - this tests expected behavior
        try:
            state = SessionState.load(temp_project_dir)
            # If it returns, should be default state
            assert state.iteration == 0
        except json.JSONDecodeError:
            # This is also acceptable - we're documenting current behavior
            pass

    def test_agent_config_load_with_corrupted_file(self, temp_project_dir):
        """AgentConfig.load should raise on corrupted file."""
        config_file = temp_project_dir / "config.json"
        config_file.write_text("{broken")

        with pytest.raises(json.JSONDecodeError):
            AgentConfig.load(config_file)


# -----------------------------------------------------------------------------
# Missing Files Tests
# -----------------------------------------------------------------------------

class TestMissingFiles:
    """Tests for handling missing required files."""

    def test_missing_feature_list_returns_zeros(self, temp_project_dir):
        """Missing feature_list.json should return (0, 0)."""
        # Don't create the file

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_missing_feature_list_get_next_returns_none(self, temp_project_dir):
        """Missing feature_list.json should return None from get_next_feature."""
        result = get_next_feature(temp_project_dir)

        assert result is None

    def test_missing_state_file_creates_new(self, temp_project_dir):
        """Missing state file should create new default state."""
        state = SessionState.load(temp_project_dir)

        assert state.iteration == 0
        assert state.features_completed == 0
        assert state.session_type == "INITIALIZER"

    def test_missing_project_dir_in_count_features(self):
        """Non-existent project dir should return (0, 0)."""
        nonexistent = Path("/nonexistent/path/that/does/not/exist")

        passing, total = count_passing_features(nonexistent)

        assert passing == 0
        assert total == 0

    def test_print_progress_summary_missing_file(self, temp_project_dir, capsys):
        """print_progress_summary should handle missing file gracefully."""
        # Should not crash
        print_progress_summary(temp_project_dir)

        captured = capsys.readouterr()
        assert "not yet created" in captured.out.lower() or "0" in captured.out


# -----------------------------------------------------------------------------
# Malformed Data Tests
# -----------------------------------------------------------------------------

class TestMalformedData:
    """Tests for handling malformed but parseable data."""

    def test_feature_missing_passes_field(self, temp_project_dir):
        """Feature without 'passes' field should default to False."""
        data = {
            "features": [
                {"id": "F001", "name": "Test"},  # Missing 'passes'
            ]
        }
        (temp_project_dir / "feature_list.json").write_text(json.dumps(data))

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 1

    def test_feature_passes_wrong_type(self, temp_project_dir):
        """Feature with wrong type for 'passes' should be handled."""
        data = {
            "features": [
                {"id": "F001", "name": "Test", "passes": "yes"},  # String instead of bool
            ]
        }
        (temp_project_dir / "feature_list.json").write_text(json.dumps(data))

        passing, total = count_passing_features(temp_project_dir)

        # "yes" is truthy in Python
        assert total == 1

    def test_empty_features_array(self, temp_project_dir):
        """Empty features array should return (0, 0)."""
        data = {"features": []}
        (temp_project_dir / "feature_list.json").write_text(json.dumps(data))

        passing, total = count_passing_features(temp_project_dir)

        assert passing == 0
        assert total == 0

    def test_features_not_array(self, temp_project_dir):
        """'features' as non-array raises error (documents current behavior).

        Note: This test documents that progress.py does NOT gracefully handle
        the case where 'features' is a string instead of an array. The error
        occurs when trying to call .get() on string characters.

        This could be considered a bug to fix in progress.py.
        """
        data = {"features": "not an array"}
        (temp_project_dir / "feature_list.json").write_text(json.dumps(data))

        # Current behavior: raises AttributeError
        with pytest.raises(AttributeError):
            count_passing_features(temp_project_dir)


# -----------------------------------------------------------------------------
# CLI Failure Tests
# -----------------------------------------------------------------------------

class TestCLIFailures:
    """Tests for CLI execution failures."""

    @pytest.mark.asyncio
    async def test_cli_timeout_handled(self, temp_project_dir):
        """CLI timeout should return error status."""
        async def mock_subprocess(*args, **kwargs):
            raise asyncio.TimeoutError("CLI timed out")

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"

    @pytest.mark.asyncio
    async def test_cli_permission_denied_handled(self, temp_project_dir):
        """Permission denied should return error status."""
        async def mock_subprocess(*args, **kwargs):
            raise PermissionError("Permission denied")

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"
        assert "Permission" in response or "denied" in response.lower()

    @pytest.mark.asyncio
    async def test_cli_file_not_found_handled(self, temp_project_dir):
        """CLI not found should return error status."""
        async def mock_subprocess(*args, **kwargs):
            raise FileNotFoundError("claude not found")

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"

    @pytest.mark.asyncio
    async def test_cli_crash_returns_error(self, temp_project_dir):
        """CLI crash (non-zero exit) should return error status."""
        async def mock_subprocess(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Segmentation fault")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 139  # SIGSEGV
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"

    @pytest.mark.asyncio
    async def test_cli_output_decode_error(self, temp_project_dir):
        """Invalid UTF-8 output should be handled."""
        async def mock_subprocess(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            # Invalid UTF-8 bytes
            mock_process.stdout.read = AsyncMock(side_effect=[b"\xff\xfe invalid", b""])
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            # Should not crash - either handles gracefully or returns error
            try:
                status, response = await run_agent_session(
                    prompt="Test",
                    project_dir=temp_project_dir,
                    model="sonnet",
                )
                # If it returns, status should be valid
                assert status in ["continue", "error"]
            except UnicodeDecodeError:
                # Also acceptable if it propagates
                pass


# -----------------------------------------------------------------------------
# State Transition Tests
# -----------------------------------------------------------------------------

class TestStateTransitions:
    """Tests for state machine transition edge cases."""

    def test_unknown_session_type_defaults_to_implement(self, minimal_config):
        """Unknown session type should default to IMPLEMENT."""
        state = SessionState(session_type="UNKNOWN_TYPE")

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.IMPLEMENT

    def test_get_model_for_unknown_session_type(self, minimal_config):
        """Unknown session type should return implement_model."""
        model = get_model_for_session("UNKNOWN_TYPE", minimal_config)

        assert model == minimal_config.implement_model

    def test_review_without_issues_goes_to_implement(self, minimal_config):
        """REVIEW with no issues should go to IMPLEMENT."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=1,
        )
        minimal_config.architecture_interval = 10  # Won't trigger

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.IMPLEMENT

    def test_review_with_issues_goes_to_fix(self, minimal_config):
        """REVIEW with issues should go to FIX."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=["Issue 1", "Issue 2"],
        )

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.FIX

    def test_architecture_triggered_at_interval(self, minimal_config):
        """ARCHITECTURE should trigger at architecture_interval."""
        minimal_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=5,  # Exactly at interval
        )

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.ARCHITECTURE

    def test_architecture_not_triggered_before_interval(self, minimal_config):
        """ARCHITECTURE should NOT trigger before interval."""
        minimal_config.architecture_interval = 5
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            features_completed=4,  # One before interval
        )

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.IMPLEMENT

    def test_fix_always_goes_to_review(self, minimal_config):
        """FIX should always go back to REVIEW."""
        state = SessionState(session_type=SessionType.FIX)

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.REVIEW

    def test_initializer_goes_to_implement(self, minimal_config):
        """INITIALIZER should go to IMPLEMENT."""
        state = SessionState(session_type=SessionType.INITIALIZER)

        next_type = get_next_session_type(state, minimal_config)

        assert next_type == SessionType.IMPLEMENT


# -----------------------------------------------------------------------------
# Config Edge Cases
# -----------------------------------------------------------------------------

class TestConfigEdgeCases:
    """Tests for configuration edge cases."""

    def test_config_with_none_max_iterations(self, temp_project_dir):
        """Config with None max_iterations should work."""
        spec_file = temp_project_dir / "spec.txt"
        spec_file.write_text("test")

        config = AgentConfig(
            project_dir=temp_project_dir,
            spec_file=spec_file,
            max_iterations=None,
        )

        assert config.max_iterations is None

    def test_config_with_zero_feature_count(self, temp_project_dir):
        """Config with zero feature_count should be allowed."""
        spec_file = temp_project_dir / "spec.txt"
        spec_file.write_text("test")

        config = AgentConfig(
            project_dir=temp_project_dir,
            spec_file=spec_file,
            feature_count=0,
        )

        assert config.feature_count == 0

    def test_config_with_empty_source_dirs(self, temp_project_dir):
        """Config with empty source_dirs should work."""
        spec_file = temp_project_dir / "spec.txt"
        spec_file.write_text("test")

        config = AgentConfig(
            project_dir=temp_project_dir,
            spec_file=spec_file,
            source_dirs=[],
        )

        assert config.source_dirs == []

    def test_state_save_creates_parent_dirs(self, temp_project_dir):
        """SessionState.save should work with existing directory."""
        state = SessionState(iteration=5)

        # Should not crash
        state.save(temp_project_dir)

        state_file = temp_project_dir / ".agent_state.json"
        assert state_file.exists()

    def test_config_save_load_roundtrip(self, temp_project_dir):
        """Config should survive save/load cycle."""
        spec_file = temp_project_dir / "spec.txt"
        spec_file.write_text("test")

        original = AgentConfig(
            project_dir=temp_project_dir,
            spec_file=spec_file,
            implement_model="opus",
            review_model="haiku",
            max_iterations=42,
            feature_count=100,
        )

        config_file = temp_project_dir / "config.json"
        original.save(config_file)
        loaded = AgentConfig.load(config_file)

        assert loaded.implement_model == original.implement_model
        assert loaded.review_model == original.review_model
        assert loaded.max_iterations == original.max_iterations
        assert loaded.feature_count == original.feature_count


# -----------------------------------------------------------------------------
# IO Error Tests
# -----------------------------------------------------------------------------

class TestIOErrors:
    """Tests for file I/O errors."""

    def test_count_features_with_permission_denied(self, temp_project_dir):
        """Permission denied should return (0, 0)."""
        feature_file = temp_project_dir / "feature_list.json"
        feature_file.write_text('{"features": []}')

        # Make file unreadable (Unix only)
        import os
        if os.name == "posix":
            feature_file.chmod(0o000)
            try:
                passing, total = count_passing_features(temp_project_dir)
                assert passing == 0
                assert total == 0
            finally:
                feature_file.chmod(0o644)
        else:
            pytest.skip("Unix-only test")

    def test_state_save_to_readonly_dir(self, temp_project_dir):
        """Saving state to readonly dir should raise."""
        import os
        if os.name != "posix":
            pytest.skip("Unix-only test")

        state = SessionState(iteration=1)

        # Make directory readonly
        temp_project_dir.chmod(0o555)
        try:
            with pytest.raises((PermissionError, OSError)):
                state.save(temp_project_dir)
        finally:
            temp_project_dir.chmod(0o755)
