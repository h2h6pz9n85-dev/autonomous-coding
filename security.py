"""
Security Configuration for Autonomous Coding Agent
===================================================

Security settings and tool allowlists for the autonomous coding agent.
Fully configurable via parameters - no hardcoded project paths.
"""

import json
from pathlib import Path


# Playwright MCP tools for browser automation
# Note: The full tool name includes the MCP server prefix
PLAYWRIGHT_TOOLS = [
    "mcp__plugin_playwright_playwright__browser_navigate",
    "mcp__plugin_playwright_playwright__browser_navigate_back",
    "mcp__plugin_playwright_playwright__browser_snapshot",
    "mcp__plugin_playwright_playwright__browser_click",
    "mcp__plugin_playwright_playwright__browser_fill_form",
    "mcp__plugin_playwright_playwright__browser_type",
    "mcp__plugin_playwright_playwright__browser_select_option",
    "mcp__plugin_playwright_playwright__browser_hover",
    "mcp__plugin_playwright_playwright__browser_drag",
    "mcp__plugin_playwright_playwright__browser_press_key",
    "mcp__plugin_playwright_playwright__browser_take_screenshot",
    "mcp__plugin_playwright_playwright__browser_evaluate",
    "mcp__plugin_playwright_playwright__browser_console_messages",
    "mcp__plugin_playwright_playwright__browser_network_requests",
    "mcp__plugin_playwright_playwright__browser_tabs",
    "mcp__plugin_playwright_playwright__browser_close",
    "mcp__plugin_playwright_playwright__browser_resize",
    "mcp__plugin_playwright_playwright__browser_file_upload",
    "mcp__plugin_playwright_playwright__browser_handle_dialog",
    "mcp__plugin_playwright_playwright__browser_wait_for",
    "mcp__plugin_playwright_playwright__browser_install",
    "mcp__plugin_playwright_playwright__browser_run_code",
]

# Built-in Claude Code tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
    "TodoWrite",
]

# Combined allowed tools list
ALLOWED_TOOLS = BUILTIN_TOOLS + PLAYWRIGHT_TOOLS

def create_settings_file(
    project_dir: Path,
    source_dirs: list[Path] = None,
    forbidden_dirs: list[Path] = None,
) -> Path:
    """
    Create security settings file for Claude Code CLI.

    Args:
        project_dir: Directory for the generated project
        source_dirs: Additional directories the agent can access
        forbidden_dirs: Directories the agent should avoid

    Returns:
        Path to the created settings file
    """
    source_dirs = source_dirs or []
    forbidden_dirs = forbidden_dirs or []

    # Build permission list
    permissions = []

    # Allow all file operations within project directory
    permissions.extend([
        f"Read({project_dir}/**)",
        f"Write({project_dir}/**)",
        f"Edit({project_dir}/**)",
        f"Glob({project_dir}/**)",
        f"Grep({project_dir}/**)",
    ])

    # Allow operations in additional source directories
    for source_dir in source_dirs:
        source_dir = source_dir.resolve()
        permissions.extend([
            f"Read({source_dir}/**)",
            f"Write({source_dir}/**)",
            f"Edit({source_dir}/**)",
            f"Glob({source_dir}/**)",
            f"Grep({source_dir}/**)",
        ])

    # Add bash command permissions
    permissions.extend([
        "Bash(ls *)",
        "Bash(cat *)",
        "Bash(npm *)",
        "Bash(npx *)",
        "Bash(node *)",
        "Bash(python *)",
        "Bash(python3 *)",
        "Bash(pip *)",
        "Bash(pip3 *)",
        "Bash(pytest *)",
        "Bash(git *)",
        "Bash(mkdir *)",
        "Bash(chmod +x *)",
        "Bash(./init.sh)",
        # Note: curl is intentionally NOT allowed to prevent bypassing UI testing
        "Bash(sleep *)",
        "Bash(date *)",
        "Bash(uvicorn *)",
    ])

    # Add Playwright browser automation permissions
    for tool in PLAYWRIGHT_TOOLS:
        permissions.append(f"{tool}(*)")

    settings = {
        "permissions": {
            "allow": permissions,
        },
        "model": "sonnet",
    }

    # Write settings file
    project_dir.mkdir(parents=True, exist_ok=True)
    settings_file = project_dir / ".claude_settings.json"

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    # Create CLAUDE.md with project rules
    claude_md = project_dir / "CLAUDE.md"
    claude_md_content = generate_claude_md(project_dir, source_dirs, forbidden_dirs)

    with open(claude_md, "w") as f:
        f.write(claude_md_content)

    return settings_file


def generate_claude_md(
    project_dir: Path,
    source_dirs: list[Path],
    forbidden_dirs: list[Path],
) -> str:
    """Generate CLAUDE.md content with project rules."""

    allowed_section = "- This project directory - Generated application files\n"
    for source_dir in source_dirs:
        allowed_section += f"- `{source_dir}` - Source code\n"

    forbidden_section = ""
    for forbidden_dir in forbidden_dirs:
        forbidden_section += f"- `{forbidden_dir}` - Do not modify\n"

    if not forbidden_section:
        forbidden_section = "- (No specific forbidden directories configured)\n"

    return f"""# Project Rules for Autonomous Coding Agent

## SCOPE CONSTRAINTS - CRITICAL

You are working on an autonomous coding project. You may ONLY modify files in:

✅ ALLOWED:
{allowed_section}
❌ DO NOT TOUCH:
{forbidden_section}
## Multi-Agent Workflow

This project uses a multi-agent workflow:

1. **IMPLEMENT** - Create feature branches, implement features, write tests
2. **REVIEW** - Review implementations against the checklist in `review_checklist.md`
3. **FIX** - Address any issues found during review
4. **ARCHITECTURE** - Periodic codebase-wide refactoring (every 5 features)

## Git Workflow

- Create a new branch for each feature: `feature/<feature-name>`
- Make atomic commits with descriptive messages
- After implementation, leave branch ready for review
- After review passes, merge to main

## Testing Requirements

- Use **Playwright** for browser automation (NOT Puppeteer)
- Test through actual UI, not just API calls
- **DO NOT use curl for testing** - All testing must go through the UI with Playwright
- Take screenshots to verify visual appearance
- Verify both functionality AND visual appearance
- Write both positive AND negative test cases

## Development Standards

- Follow TDD: Write failing test first, then implement
- Follow SOLID principles
- No lazy implementations (no TODOs, no stubs, no mocks in production code)
- All features must work end-to-end through the UI
- Commit progress frequently with descriptive messages

## Quality Bar

- Zero console errors
- Mobile responsive
- Fast and professional UI
- All features work end-to-end through the UI
- Code passes review checklist
"""


