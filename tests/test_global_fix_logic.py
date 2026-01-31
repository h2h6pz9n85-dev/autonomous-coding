
import pytest
from unittest.mock import MagicMock, patch
from config import AgentConfig, SessionState, SessionType, get_next_session_type
from prompts import get_fix_prompt

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def base_config():
    """Create a basic AgentConfig for testing."""
    return AgentConfig(
        project_dir=".",
        spec_file="app_spec.txt",
        implement_model="sonnet",
        review_model="opus",
        fix_model="sonnet",
        architecture_model="opus",
        architecture_interval=5,
        feature_count=10,
        main_branch="main",
    )

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

class TestGlobalFixScheduling:
    """Test the scheduling logic for the Global Technical Debt Fix agent."""

    def test_session_state_has_new_fields(self):
        """SessionState should have total_implementations and last_global_fix_implementation_count."""
        state = SessionState()
        assert hasattr(state, "total_implementations")
        assert hasattr(state, "last_global_fix_implementation_count")
        assert state.total_implementations == 0
        assert state.last_global_fix_implementation_count == 0

    def test_does_not_trigger_before_interval(self, base_config):
        """Should NOT trigger Global Fix if interval < 10."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],  # Passing review
            total_implementations=9,
            last_global_fix_implementation_count=0,
        )
        
        # Should go to IMPLEMENT (or ARCHITECTURE), but NOT FIX
        next_type = get_next_session_type(state, base_config)
        assert next_type != SessionType.FIX

    def test_triggers_at_interval_after_pass(self, base_config):
        """Should trigger Global Fix if interval >= 10 and review passed."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],  # Passing review
            total_implementations=10,
            last_global_fix_implementation_count=0,
        )
        
        # Should go to FIX (Global)
        next_type = get_next_session_type(state, base_config)
        assert next_type == SessionType.FIX

    def test_does_not_trigger_if_review_failed(self, base_config):
        """Should NOT trigger Global Fix if review failed (Normal Fix takes precedence)."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=["Some issue"],  # Failing review
            total_implementations=10,
            last_global_fix_implementation_count=0,
        )
        
        # Should go to FIX, but logic in config.py handles both via FIX type.
        # The key is that later prompt selection distinguishes them.
        next_type = get_next_session_type(state, base_config)
        assert next_type == SessionType.FIX

    def test_resets_interval_logic(self, base_config):
        """Should NOT trigger if recently ran."""
        state = SessionState(
            session_type=SessionType.REVIEW,
            review_issues=[],
            total_implementations=15,
            last_global_fix_implementation_count=10,  # Ran at 10
        )
        
        # 15 - 10 = 5 < 10, so should NOT trigger
        next_type = get_next_session_type(state, base_config)
        assert next_type != SessionType.FIX


class TestGlobalFixPromptSelection:
    """Test the prompt selection logic for Global Fix vs Normal Fix."""

    @patch("prompts.load_prompt_template")
    def test_selects_global_fix_prompt_when_no_issues(self, mock_load, base_config):
        """If review_issues is empty, use global_fix_prompt."""
        mock_load.return_value = "Template content"
        
        state = SessionState(
            session_type=SessionType.FIX,
            review_issues=[],  # Empty means Global Fix context
        )
        
        get_fix_prompt(base_config, state)
        
        mock_load.assert_called_with("global_fix_prompt")

    @patch("prompts.load_prompt_template")
    def test_selects_normal_fix_prompt_when_issues_exist(self, mock_load, base_config):
        """If review_issues exist, use fix_prompt."""
        mock_load.return_value = "Template content"
        
        state = SessionState(
            session_type=SessionType.FIX,
            review_issues=["Bug 1"],  # Has issues
        )
        
        get_fix_prompt(base_config, state)
        
        mock_load.assert_called_with("fix_prompt")
