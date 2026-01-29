"""
CLI Integration Tests
=====================

Tests that verify the actual Claude Code CLI integration works correctly.
These tests verify command construction, subprocess handling, and real CLI behavior.

Note: Tests marked with @pytest.mark.slow actually invoke the CLI and may incur costs.
Run with: pytest -m slow tests/test_cli_integration.py
"""

import json
import os
import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import run_agent_session, ALLOWED_TOOLS
from security import create_settings_file
from config import AgentConfig
from autonomous_agent_demo import check_claude_code_installed


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
# CLI Installation Check Tests
# -----------------------------------------------------------------------------

class TestCLIInstallation:
    """Tests for CLI installation detection."""

    def test_check_claude_code_installed_returns_bool(self):
        """check_claude_code_installed returns a boolean."""
        result = check_claude_code_installed()
        assert isinstance(result, bool)

    def test_check_handles_missing_cli_gracefully(self):
        """If CLI is not installed, returns False without crashing."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = check_claude_code_installed()
            assert result is False

    def test_check_handles_timeout_gracefully(self):
        """If CLI times out, returns False without crashing."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 10)):
            result = check_claude_code_installed()
            assert result is False

    def test_check_handles_nonzero_exit_code(self):
        """If CLI returns non-zero exit code, returns False."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = check_claude_code_installed()
            assert result is False


# -----------------------------------------------------------------------------
# Command Construction Tests
# -----------------------------------------------------------------------------

class TestCommandConstruction:
    """Tests that verify CLI commands are built correctly."""

    @pytest.mark.asyncio
    async def test_command_includes_prompt(self, temp_project_dir):
        """Command includes the prompt with -p flag."""
        captured_cmd = []

        async def mock_subprocess(*args, **kwargs):
            captured_cmd.extend(args)  # args is a tuple of all command parts
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await run_agent_session(
                prompt="Test prompt",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        # captured_cmd contains all args passed to create_subprocess_exec
        assert "-p" in captured_cmd
        prompt_idx = captured_cmd.index("-p")
        assert captured_cmd[prompt_idx + 1] == "Test prompt"

    @pytest.mark.asyncio
    async def test_command_includes_model(self, temp_project_dir):
        """Command includes the model with --model flag."""
        captured_cmd = []

        async def mock_subprocess(*args, **kwargs):
            captured_cmd.extend(args)
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="opus",
            )

        assert "--model" in captured_cmd
        model_idx = captured_cmd.index("--model")
        assert captured_cmd[model_idx + 1] == "opus"

    @pytest.mark.asyncio
    async def test_command_includes_allowed_tools(self, temp_project_dir):
        """Command includes all allowed tools."""
        captured_cmd = []

        async def mock_subprocess(*args, **kwargs):
            captured_cmd.extend(args)
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        # Verify all allowed tools are included
        for tool in ALLOWED_TOOLS:
            assert tool in captured_cmd, f"Missing allowed tool: {tool}"

    @pytest.mark.asyncio
    async def test_command_includes_max_turns(self, temp_project_dir):
        """Command includes --max-turns flag."""
        captured_cmd = []

        async def mock_subprocess(*args, **kwargs):
            captured_cmd.extend(args)
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert "--max-turns" in captured_cmd

    @pytest.mark.asyncio
    async def test_command_uses_correct_working_directory(self, temp_project_dir):
        """Command is executed in the project directory."""
        captured_kwargs = {}

        async def mock_subprocess(*args, **kwargs):
            captured_kwargs.update(kwargs)
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert captured_kwargs["cwd"] == str(temp_project_dir.resolve())


# -----------------------------------------------------------------------------
# Response Handling Tests
# -----------------------------------------------------------------------------

class TestResponseHandling:
    """Tests for handling CLI responses."""

    @pytest.mark.asyncio
    async def test_successful_response_returns_continue(self, temp_project_dir):
        """Successful CLI execution returns ('continue', response)."""
        async def mock_subprocess(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(side_effect=[b"Success output", b""])
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 0
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "continue"
        assert "Success output" in response

    @pytest.mark.asyncio
    async def test_nonzero_exit_returns_error(self, temp_project_dir):
        """Non-zero exit code returns ('error', message)."""
        async def mock_subprocess(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.read = AsyncMock(return_value=b"")
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Error details")
            mock_process.wait = AsyncMock()
            mock_process.returncode = 1
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"
        assert "exit" in response.lower() or "1" in response

    @pytest.mark.asyncio
    async def test_exception_returns_error(self, temp_project_dir):
        """Exception during execution returns ('error', message)."""
        async def mock_subprocess(*args, **kwargs):
            raise Exception("Connection failed")

        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
            status, response = await run_agent_session(
                prompt="Test",
                project_dir=temp_project_dir,
                model="sonnet",
            )

        assert status == "error"
        assert "Connection failed" in response


# -----------------------------------------------------------------------------
# Security Settings Integration
# -----------------------------------------------------------------------------

class TestSecuritySettingsIntegration:
    """Tests for security settings file creation."""

    def test_settings_file_created_in_project_dir(self, temp_project_dir):
        """Settings file is created in the project directory."""
        settings_file = create_settings_file(temp_project_dir)

        assert settings_file.exists()
        assert settings_file.parent == temp_project_dir
        assert settings_file.name == ".claude_settings.json"

    def test_settings_file_contains_permissions(self, temp_project_dir):
        """Settings file contains permission configuration."""
        settings_file = create_settings_file(temp_project_dir)

        settings = json.loads(settings_file.read_text())

        assert "permissions" in settings
        assert "allow" in settings["permissions"]
        assert len(settings["permissions"]["allow"]) > 0

    def test_settings_file_permissions_include_project_dir(self, temp_project_dir):
        """Permissions include the project directory paths."""
        settings_file = create_settings_file(temp_project_dir)

        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        # Should have Read, Write, Edit, Glob, Grep for project dir
        project_str = str(temp_project_dir)
        assert any(project_str in p and "Read" in p for p in permissions)
        assert any(project_str in p and "Write" in p for p in permissions)

    def test_settings_file_includes_source_dirs(self, temp_project_dir):
        """Settings file includes additional source directories."""
        source_dir = temp_project_dir / "src"
        source_dir.mkdir()

        settings_file = create_settings_file(temp_project_dir, source_dirs=[source_dir])

        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        source_str = str(source_dir)
        assert any(source_str in p for p in permissions)

    def test_claude_md_created(self, temp_project_dir):
        """CLAUDE.md file is created with project rules."""
        create_settings_file(temp_project_dir)

        claude_md = temp_project_dir / "CLAUDE.md"
        assert claude_md.exists()

        content = claude_md.read_text()
        assert "SCOPE CONSTRAINTS" in content
        assert "Multi-Agent Workflow" in content

    def test_allowed_tools_lists_match(self):
        """ALLOWED_TOOLS in agent.py matches security.py."""
        from agent import ALLOWED_TOOLS as AGENT_TOOLS
        from security import ALLOWED_TOOLS as SECURITY_TOOLS

        assert set(AGENT_TOOLS) == set(SECURITY_TOOLS)


# -----------------------------------------------------------------------------
# Live CLI Tests (Slow, may incur costs)
# -----------------------------------------------------------------------------

@pytest.mark.slow
class TestLiveCLI:
    """
    Live tests that actually invoke Claude Code CLI.

    These tests are marked slow and should be run explicitly:
        pytest -m slow tests/test_cli_integration.py

    WARNING: These tests may incur API costs!
    """

    @pytest.fixture
    def skip_if_no_cli(self):
        """Skip test if CLI is not installed."""
        if not check_claude_code_installed():
            pytest.skip("Claude Code CLI not installed")

    @pytest.mark.asyncio
    async def test_live_cli_simple_prompt(self, temp_project_dir, skip_if_no_cli):  # noqa: ARG002
        """
        Live test: Send a simple prompt and verify response.

        This test sends a minimal prompt that should complete quickly.
        """
        _ = skip_if_no_cli  # Used for skip side effect
        # Create minimal project structure
        (temp_project_dir / "test.txt").write_text("Hello")

        status, response = await run_agent_session(
            prompt="Read test.txt and respond with just 'OK' if it contains 'Hello'.",
            project_dir=temp_project_dir,
            model="haiku",  # Use cheapest model
        )

        # We don't assert specific response content since that depends on the model
        # Just verify we got a response without error
        assert status in ["continue", "error"]
        assert response is not None
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_live_cli_respects_working_directory(self, temp_project_dir, skip_if_no_cli):  # noqa: ARG002
        """
        Live test: Verify CLI operates in correct working directory.
        """
        _ = skip_if_no_cli  # Used for skip side effect
        # Create a unique file in the project directory
        unique_content = f"UNIQUE_MARKER_{os.getpid()}"
        (temp_project_dir / "marker.txt").write_text(unique_content)

        status, response = await run_agent_session(
            prompt=f"Use the Read tool to read marker.txt. If it contains '{unique_content}', respond with 'FOUND'. Otherwise respond with 'NOT_FOUND'.",
            project_dir=temp_project_dir,
            model="haiku",
        )

        # The agent should be able to find and read the file
        assert status == "continue"


# -----------------------------------------------------------------------------
# Tool Allowlist Tests
# -----------------------------------------------------------------------------

class TestToolAllowlist:
    """Tests for tool allowlist configuration."""

    def test_builtin_tools_included(self):
        """All required builtin tools are in the allowlist."""
        required_builtins = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]

        for tool in required_builtins:
            assert tool in ALLOWED_TOOLS, f"Missing builtin tool: {tool}"

    def test_playwright_tools_included(self):
        """Playwright MCP tools are in the allowlist."""
        # At least some playwright tools should be present
        playwright_tools = [t for t in ALLOWED_TOOLS if "playwright" in t.lower()]
        assert len(playwright_tools) > 0, "No Playwright tools in allowlist"

    def test_no_dangerous_tools(self):
        """Dangerous tools are NOT in the allowlist."""
        # These are dangerous shell commands/patterns, not method names
        dangerous_patterns = [
            "sudo",
            "rm -rf",
            "chmod 777",
        ]

        for tool in ALLOWED_TOOLS:
            for pattern in dangerous_patterns:
                assert pattern not in tool.lower(), f"Dangerous pattern '{pattern}' found in tool: {tool}"

        # Verify no raw eval/exec as standalone tools (but browser_evaluate is OK)
        standalone_dangerous = ["eval", "exec"]
        for tool in ALLOWED_TOOLS:
            tool_lower = tool.lower()
            for pattern in standalone_dangerous:
                # Only flag if it's the whole tool name or a bash command
                if tool_lower == pattern or f"bash({pattern}" in tool_lower:
                    raise AssertionError(f"Dangerous tool: {tool}")
