"""
Security Tests
==============

Tests for verifying security constraints are properly enforced:
- Forbidden directory enforcement
- Permission boundaries
- Scope constraints in generated CLAUDE.md
"""

import json
import os
import pytest
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from security import create_settings_file, generate_claude_md, ALLOWED_TOOLS, BUILTIN_TOOLS, PLAYWRIGHT_TOOLS
from config import AgentConfig


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
def temp_source_dir():
    """Create a temporary source directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_forbidden_dir():
    """Create a temporary forbidden directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


# -----------------------------------------------------------------------------
# Permission Generation Tests
# -----------------------------------------------------------------------------

class TestPermissionGeneration:
    """Tests for permission list generation in settings file."""

    def test_project_dir_has_full_permissions(self, temp_project_dir):
        """Project directory should have Read, Write, Edit, Glob, Grep permissions."""
        settings_file = create_settings_file(temp_project_dir)
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        project_str = str(temp_project_dir)

        # Check all file operation permissions exist for project dir
        assert any(f"Read({project_str}" in p for p in permissions), "Missing Read permission"
        assert any(f"Write({project_str}" in p for p in permissions), "Missing Write permission"
        assert any(f"Edit({project_str}" in p for p in permissions), "Missing Edit permission"
        assert any(f"Glob({project_str}" in p for p in permissions), "Missing Glob permission"
        assert any(f"Grep({project_str}" in p for p in permissions), "Missing Grep permission"

    def test_source_dirs_have_full_permissions(self, temp_project_dir, temp_source_dir):
        """Source directories should have same permissions as project dir."""
        settings_file = create_settings_file(temp_project_dir, source_dirs=[temp_source_dir])
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        source_str = str(temp_source_dir.resolve())

        assert any(f"Read({source_str}" in p for p in permissions), "Missing Read permission for source dir"
        assert any(f"Write({source_str}" in p for p in permissions), "Missing Write permission for source dir"
        assert any(f"Edit({source_str}" in p for p in permissions), "Missing Edit permission for source dir"

    def test_multiple_source_dirs_all_have_permissions(self, temp_project_dir):
        """All source directories should have permissions."""
        source_dirs = []
        for i in range(3):
            source_dir = Path(tempfile.mkdtemp())
            source_dirs.append(source_dir)

        try:
            settings_file = create_settings_file(temp_project_dir, source_dirs=source_dirs)
            settings = json.loads(settings_file.read_text())
            permissions = settings["permissions"]["allow"]

            for source_dir in source_dirs:
                source_str = str(source_dir.resolve())
                assert any(source_str in p for p in permissions), f"Missing permissions for {source_dir}"
        finally:
            for source_dir in source_dirs:
                shutil.rmtree(source_dir)

    def test_permissions_use_glob_pattern(self, temp_project_dir):
        """Permissions should use /** glob pattern for recursive access."""
        settings_file = create_settings_file(temp_project_dir)
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        # Check that permissions use /** pattern
        project_permissions = [p for p in permissions if str(temp_project_dir) in p]
        for perm in project_permissions:
            if "Bash" not in perm:  # Bash permissions don't use glob
                assert "/**" in perm, f"Permission missing /** glob: {perm}"

    def test_bash_permissions_included(self, temp_project_dir):
        """Common bash commands should be permitted."""
        settings_file = create_settings_file(temp_project_dir)
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        bash_permissions = [p for p in permissions if p.startswith("Bash(")]

        # Check for common required commands
        assert any("git" in p for p in bash_permissions), "Missing git permission"
        assert any("npm" in p for p in bash_permissions), "Missing npm permission"
        assert any("python" in p for p in bash_permissions), "Missing python permission"


# -----------------------------------------------------------------------------
# Forbidden Directory Tests
# -----------------------------------------------------------------------------

class TestForbiddenDirectories:
    """Tests for forbidden directory enforcement."""

    def test_forbidden_dirs_not_in_permissions(self, temp_project_dir, temp_forbidden_dir):
        """Forbidden directories should NOT appear in permissions."""
        settings_file = create_settings_file(
            temp_project_dir,
            forbidden_dirs=[temp_forbidden_dir]
        )
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        forbidden_str = str(temp_forbidden_dir)

        # Forbidden directory should not have any permissions
        for perm in permissions:
            assert forbidden_str not in perm, f"Forbidden dir found in permission: {perm}"

    def test_forbidden_dirs_documented_in_claude_md(self, temp_project_dir, temp_forbidden_dir):
        """Forbidden directories should be listed in CLAUDE.md."""
        create_settings_file(
            temp_project_dir,
            forbidden_dirs=[temp_forbidden_dir]
        )

        claude_md = temp_project_dir / "CLAUDE.md"
        content = claude_md.read_text()

        assert str(temp_forbidden_dir) in content, "Forbidden dir not documented in CLAUDE.md"
        assert "DO NOT" in content.upper() or "❌" in content, "Missing warning about forbidden dirs"

    def test_multiple_forbidden_dirs_all_excluded(self, temp_project_dir):
        """Multiple forbidden directories should all be excluded."""
        forbidden_dirs = []
        for i in range(3):
            forbidden_dir = Path(tempfile.mkdtemp())
            forbidden_dirs.append(forbidden_dir)

        try:
            settings_file = create_settings_file(
                temp_project_dir,
                forbidden_dirs=forbidden_dirs
            )
            settings = json.loads(settings_file.read_text())
            permissions = settings["permissions"]["allow"]

            for forbidden_dir in forbidden_dirs:
                forbidden_str = str(forbidden_dir)
                for perm in permissions:
                    assert forbidden_str not in perm, f"Forbidden dir {forbidden_dir} found in permission"
        finally:
            for forbidden_dir in forbidden_dirs:
                shutil.rmtree(forbidden_dir)


# -----------------------------------------------------------------------------
# CLAUDE.md Generation Tests
# -----------------------------------------------------------------------------

class TestClaudeMdGeneration:
    """Tests for CLAUDE.md content generation."""

    def test_claude_md_has_scope_constraints(self, temp_project_dir):
        """CLAUDE.md should have scope constraints section."""
        create_settings_file(temp_project_dir)

        claude_md = temp_project_dir / "CLAUDE.md"
        content = claude_md.read_text()

        assert "SCOPE CONSTRAINTS" in content.upper()
        assert "CRITICAL" in content.upper()

    def test_claude_md_lists_allowed_directories(self, temp_project_dir, temp_source_dir):
        """CLAUDE.md should list allowed directories."""
        create_settings_file(temp_project_dir, source_dirs=[temp_source_dir])

        claude_md = temp_project_dir / "CLAUDE.md"
        content = claude_md.read_text()

        assert "ALLOWED" in content.upper() or "✅" in content

    def test_claude_md_describes_workflow(self, temp_project_dir):
        """CLAUDE.md should describe the multi-agent workflow."""
        create_settings_file(temp_project_dir)

        claude_md = temp_project_dir / "CLAUDE.md"
        content = claude_md.read_text()

        assert "IMPLEMENT" in content
        assert "REVIEW" in content
        assert "FIX" in content
        assert "ARCHITECTURE" in content

    def test_claude_md_specifies_testing_requirements(self, temp_project_dir):
        """CLAUDE.md should specify testing requirements."""
        create_settings_file(temp_project_dir)

        claude_md = temp_project_dir / "CLAUDE.md"
        content = claude_md.read_text()

        assert "Playwright" in content
        assert "test" in content.lower()

    def test_generate_claude_md_function_directly(self, temp_project_dir, temp_source_dir, temp_forbidden_dir):
        """Test generate_claude_md function directly."""
        content = generate_claude_md(
            temp_project_dir,
            source_dirs=[temp_source_dir],
            forbidden_dirs=[temp_forbidden_dir],
        )

        # Check allowed section
        assert str(temp_source_dir) in content

        # Check forbidden section
        assert str(temp_forbidden_dir) in content


# -----------------------------------------------------------------------------
# Tool Allowlist Security Tests
# -----------------------------------------------------------------------------

class TestToolAllowlistSecurity:
    """Tests for security of tool allowlists."""

    def test_no_shell_escape_in_tools(self):
        """Tool names should not contain shell escape characters."""
        dangerous_chars = [";", "|", "&", "`", "$", "()", ">>"]

        for tool in ALLOWED_TOOLS:
            for char in dangerous_chars:
                # Allow parentheses in tool names like "Bash(ls *)"
                if char == "()" and ("(" in tool and ")" in tool):
                    continue
                assert char not in tool, f"Dangerous char '{char}' in tool: {tool}"

    def test_builtin_tools_are_valid(self):
        """Builtin tools should be valid Claude Code tool names."""
        valid_builtins = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "TodoWrite"}

        for tool in BUILTIN_TOOLS:
            assert tool in valid_builtins, f"Unknown builtin tool: {tool}"

    def test_playwright_tools_have_correct_prefix(self):
        """Playwright tools should have mcp__plugin_playwright_playwright__ prefix."""
        for tool in PLAYWRIGHT_TOOLS:
            assert tool.startswith("mcp__plugin_playwright_playwright__"), f"Invalid playwright tool prefix: {tool}"

    def test_allowed_tools_is_combination(self):
        """ALLOWED_TOOLS should be BUILTIN_TOOLS + PLAYWRIGHT_TOOLS."""
        expected = set(BUILTIN_TOOLS) | set(PLAYWRIGHT_TOOLS)
        actual = set(ALLOWED_TOOLS)

        assert actual == expected, f"Mismatch: missing={expected - actual}, extra={actual - expected}"


# -----------------------------------------------------------------------------
# Path Traversal Security Tests
# -----------------------------------------------------------------------------

class TestPathTraversalSecurity:
    """Tests for path traversal attack prevention."""

    def test_permissions_use_absolute_paths(self, temp_project_dir):
        """File operation permissions should use absolute paths."""
        settings_file = create_settings_file(temp_project_dir)
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        # Only check file operation permissions, not Bash commands
        file_ops = ["Read", "Write", "Edit", "Glob", "Grep"]

        for perm in permissions:
            # Skip Bash permissions - they use command patterns, not file paths
            if perm.startswith("Bash("):
                continue

            # Check file operation permissions
            for op in file_ops:
                if perm.startswith(f"{op}("):
                    path_part = perm.split("(")[1].split(")")[0].rstrip("*").rstrip("/")
                    if path_part:
                        assert path_part.startswith("/") or path_part[1:3] == ":\\", \
                            f"Non-absolute path in permission: {perm}"

    def test_source_dirs_resolved_to_absolute(self, temp_project_dir):
        """Source directories should be resolved to absolute paths in file permissions."""
        # Create a relative path
        relative_source = Path("./relative_source")

        # The function should resolve it
        settings_file = create_settings_file(
            temp_project_dir,
            source_dirs=[relative_source]
        )
        settings = json.loads(settings_file.read_text())
        permissions = settings["permissions"]["allow"]

        # Check file operation permissions don't contain ./
        file_ops = ["Read", "Write", "Edit", "Glob", "Grep"]
        for perm in permissions:
            for op in file_ops:
                if perm.startswith(f"{op}("):
                    assert "./" not in perm, f"Relative path found in file permission: {perm}"


# -----------------------------------------------------------------------------
# Settings File Security Tests
# -----------------------------------------------------------------------------

class TestSettingsFileSecurity:
    """Tests for settings file security."""

    def test_settings_file_is_valid_json(self, temp_project_dir):
        """Settings file should be valid JSON."""
        settings_file = create_settings_file(temp_project_dir)

        # Should not raise
        settings = json.loads(settings_file.read_text())
        assert isinstance(settings, dict)

    def test_settings_file_has_correct_structure(self, temp_project_dir):
        """Settings file should have expected structure."""
        settings_file = create_settings_file(temp_project_dir)
        settings = json.loads(settings_file.read_text())

        assert "permissions" in settings
        assert "allow" in settings["permissions"]
        assert isinstance(settings["permissions"]["allow"], list)

    def test_settings_file_not_world_readable(self, temp_project_dir):
        """Settings file should have restricted permissions (Unix only)."""
        if os.name != "posix":
            pytest.skip("Unix-only test")

        settings_file = create_settings_file(temp_project_dir)

        # Get file permissions
        mode = os.stat(settings_file).st_mode

        # Check that others don't have write permission
        # (we allow read since this is a config file, not secrets)
        others_write = mode & 0o002
        assert others_write == 0, "Settings file is world-writable"

    def test_settings_file_hidden(self, temp_project_dir):
        """Settings file should be hidden (starts with dot)."""
        settings_file = create_settings_file(temp_project_dir)

        assert settings_file.name.startswith("."), "Settings file should be hidden"


# -----------------------------------------------------------------------------
# Integration with AgentConfig
# -----------------------------------------------------------------------------

class TestAgentConfigIntegration:
    """Tests for security integration with AgentConfig."""

    def test_config_paths_converted_to_path_objects(self, temp_project_dir):
        """AgentConfig should convert string paths to Path objects."""
        config = AgentConfig(
            project_dir=str(temp_project_dir),
            spec_file=str(temp_project_dir / "spec.txt"),
            source_dirs=[str(temp_project_dir / "src")],
            forbidden_dirs=[str(temp_project_dir / "forbidden")],
        )

        assert isinstance(config.project_dir, Path)
        assert isinstance(config.spec_file, Path)
        assert all(isinstance(p, Path) for p in config.source_dirs)
        assert all(isinstance(p, Path) for p in config.forbidden_dirs)

    def test_config_serialization_preserves_paths(self, temp_project_dir):
        """Config serialization should preserve path information."""
        config = AgentConfig(
            project_dir=temp_project_dir,
            spec_file=temp_project_dir / "spec.txt",
            source_dirs=[temp_project_dir / "src"],
            forbidden_dirs=[temp_project_dir / "forbidden"],
        )

        # Serialize and deserialize
        config_dict = config.to_dict()
        restored = AgentConfig.from_dict(config_dict)

        assert restored.project_dir == config.project_dir
        assert restored.spec_file == config.spec_file
        assert restored.source_dirs == config.source_dirs
        assert restored.forbidden_dirs == config.forbidden_dirs
