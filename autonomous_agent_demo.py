#!/usr/bin/env python3
"""
Autonomous Coding Agent
=======================

A reusable framework for long-running autonomous coding with Claude Code CLI.
Implements a multi-agent pattern with separate roles:

- IMPLEMENT (Sonnet): Creates feature branches, implements features
- REVIEW (Opus): Reviews implementations against best practices
- FIX (Sonnet): Addresses review feedback
- ARCHITECTURE (Opus): Periodic codebase-wide reviews

Usage:
    # Basic usage with spec file
    python autonomous_agent_demo.py \\
        --spec-file ./app_spec.txt \\
        --project-dir ./generations/my_project

    # Full configuration
    python autonomous_agent_demo.py \\
        --spec-file ./app_spec.txt \\
        --project-dir ./generations/my_project \\
        --source-dir ./src \\
        --source-dir ./lib \\
        --implement-model sonnet \\
        --review-model opus \\
        --architecture-interval 5 \\
        --max-iterations 20
"""

import argparse
import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import AgentConfig, SessionState, SessionType, get_next_session_type, get_model_for_session


def timestamp() -> str:
    """Get current timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(message: str, level: str = "INFO") -> None:
    """Log a message with timestamp."""
    print(f"[{timestamp()}] [{level}] {message}", flush=True)
from agent import run_agent_session
from prompts import (
    get_initializer_prompt,
    get_implement_prompt,
    get_review_prompt,
    get_fix_prompt,
    get_architecture_prompt,
    copy_spec_to_project,
    copy_scripts_to_project,
)
from security import create_settings_file
from progress import print_session_header, print_progress_summary


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent - Multi-agent framework using Claude Code CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Minimal usage
  python autonomous_agent_demo.py --spec-file ./app_spec.txt

  # Full configuration
  python autonomous_agent_demo.py \\
      --spec-file ./app_spec.txt \\
      --project-dir ./generations/my_project \\
      --source-dir ./src \\
      --source-dir ./lib/shared \\
      --implement-model sonnet \\
      --review-model opus \\
      --architecture-model opus \\
      --architecture-interval 5 \\
      --feature-count 50 \\
      --max-iterations 100

  # Quick test run
  python autonomous_agent_demo.py \\
      --spec-file ./app_spec.txt \\
      --max-iterations 3

Prerequisites:
  - Claude Code CLI installed: npm install -g @anthropic-ai/claude-code
  - Logged in: claude login (uses your Claude Max subscription)
        """,
    )

    # Required arguments
    parser.add_argument(
        "--spec-file",
        type=Path,
        required=True,
        help="Path to the application specification file (app_spec.txt)",
    )

    # Project configuration
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./generations/project"),
        help="Directory for generated project (default: ./generations/project)",
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        action="append",
        dest="source_dirs",
        default=[],
        help="Additional source directories the agent can modify (can be specified multiple times)",
    )

    parser.add_argument(
        "--forbidden-dir",
        type=Path,
        action="append",
        dest="forbidden_dirs",
        default=[],
        help="Directories the agent should NOT modify (can be specified multiple times)",
    )

    # Model configuration
    parser.add_argument(
        "--implement-model",
        type=str,
        default="sonnet",
        help="Model for implementation sessions (default: sonnet)",
    )

    parser.add_argument(
        "--review-model",
        type=str,
        default="opus",
        help="Model for code review sessions (default: opus)",
    )

    parser.add_argument(
        "--fix-model",
        type=str,
        default="sonnet",
        help="Model for fixing review issues (default: sonnet)",
    )

    parser.add_argument(
        "--architecture-model",
        type=str,
        default="opus",
        help="Model for architecture reviews (default: opus)",
    )

    # Session configuration
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--architecture-interval",
        type=int,
        default=5,
        help="Run architecture review every N completed features (default: 5)",
    )

    parser.add_argument(
        "--feature-count",
        type=int,
        default=50,
        help="Number of features to generate in initializer (default: 50)",
    )

    parser.add_argument(
        "--main-branch",
        type=str,
        default="main",
        help="Name of the main git branch (default: main)",
    )

    # Resume from config
    parser.add_argument(
        "--config-file",
        type=Path,
        default=None,
        help="Load configuration from JSON file (overrides other args)",
    )

    return parser.parse_args()


def check_claude_code_installed() -> bool:
    """Check if Claude Code CLI is installed."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def create_config_from_args(args: argparse.Namespace) -> AgentConfig:
    """Create AgentConfig from parsed arguments."""
    # If config file specified, load from there
    if args.config_file and args.config_file.exists():
        config = AgentConfig.load(args.config_file)
        # Override with any explicitly provided args
        if args.max_iterations is not None:
            config.max_iterations = args.max_iterations
        return config

    return AgentConfig(
        project_dir=args.project_dir,
        spec_file=args.spec_file,
        source_dirs=args.source_dirs or [],
        forbidden_dirs=args.forbidden_dirs or [],
        implement_model=args.implement_model,
        review_model=args.review_model,
        fix_model=args.fix_model,
        architecture_model=args.architecture_model,
        max_iterations=args.max_iterations,
        architecture_interval=args.architecture_interval,
        feature_count=args.feature_count,
        main_branch=args.main_branch,
    )


def get_prompt_for_session(session_type: str, config: AgentConfig, state: SessionState) -> str:
    """Get the appropriate prompt for a session type."""
    if session_type == SessionType.INITIALIZER:
        return get_initializer_prompt(config)
    elif session_type == SessionType.IMPLEMENT:
        return get_implement_prompt(config, state)
    elif session_type == SessionType.REVIEW:
        return get_review_prompt(config, state)
    elif session_type == SessionType.FIX:
        return get_fix_prompt(config, state)
    elif session_type == SessionType.ARCHITECTURE:
        return get_architecture_prompt(config, state)
    else:
        return get_implement_prompt(config, state)


async def run_autonomous_agent(config: AgentConfig) -> None:
    """
    Run the autonomous agent loop with multi-agent workflow.

    Session flow:
    1. INITIALIZER: Creates feature_list.json (first run only)
    2. IMPLEMENT: Creates branch, implements feature
    3. REVIEW: Reviews implementation, identifies issues
    4. FIX: Addresses review issues (if any)
    5. ARCHITECTURE: Periodic codebase review (every N features)
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT")
    print("  Multi-Agent Workflow with Code Review")
    print("=" * 70)
    log("Starting autonomous coding agent")
    log(f"Spec file: {config.spec_file}")
    log(f"Project directory: {config.project_dir}")
    if config.source_dirs:
        log(f"Source directories: {', '.join(str(p) for p in config.source_dirs)}")
    print(f"\nModels:")
    print(f"  - Implement: {config.implement_model}")
    print(f"  - Review: {config.review_model}")
    print(f"  - Fix: {config.fix_model}")
    print(f"  - Architecture: {config.architecture_model} (every {config.architecture_interval} features)")
    if config.max_iterations:
        print(f"\nMax iterations: {config.max_iterations}")
    print()

    # Create project directory
    config.project_dir.mkdir(parents=True, exist_ok=True)
    log(f"Project directory ready: {config.project_dir}")

    # Create security settings
    settings_file = create_settings_file(config.project_dir, config.source_dirs, config.forbidden_dirs)
    log(f"Created security settings at {settings_file}")

    # Save config for resume capability
    config.save(config.project_dir / ".agent_config.json")
    log("Saved agent config for resume capability")

    # Load or create session state
    state = SessionState.load(config.project_dir)
    log(f"Loaded session state: iteration={state.iteration}, type={state.session_type}")

    # Check if this is a fresh start by looking for feature_list.json and progress.json
    feature_list_file = config.project_dir / "feature_list.json"
    progress_file = config.project_dir / "progress.json"
    is_first_run = not feature_list_file.exists()
    can_resume = feature_list_file.exists() and progress_file.exists()

    if is_first_run:
        state.session_type = SessionType.INITIALIZER
        log("Fresh start detected - will use INITIALIZER agent")
        print()
        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is generating detailed test cases.")
        print("=" * 70)
        print()
        # Copy the app spec into the project directory
        copy_spec_to_project(config.spec_file, config.project_dir)
        log("Copied spec file to project directory")
        # Copy scripts folder so agents can access them
        copy_scripts_to_project(config.project_dir)
        log("Copied scripts folder to project directory")
    elif can_resume:
        log("Resuming existing project from progress.json")
        # Read progress.json to determine the current phase
        import json
        try:
            with open(progress_file) as f:
                progress_data = json.load(f)
            status = progress_data.get("status", {})
            current_phase = status.get("current_phase", "IMPLEMENT")
            current_feature = status.get("current_feature")
            current_branch = status.get("current_branch")
            
            # Update state from progress.json
            state.session_type = current_phase
            if current_feature:
                state.current_feature = current_feature
            if current_branch:
                state.current_branch = current_branch
            log(f"Resuming from phase: {current_phase}")
            if current_feature:
                log(f"Current feature: {current_feature}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            log(f"Could not parse progress.json, starting fresh: {e}", "WARN")
            state.session_type = SessionType.IMPLEMENT
        
        # Ensure scripts folder exists even for resumed projects
        copy_scripts_to_project(config.project_dir)
        print_progress_summary(config.project_dir)
    else:
        log("Resuming existing project")
        log(f"Current state: {state.session_type}")
        # Ensure scripts folder exists
        copy_scripts_to_project(config.project_dir)
        print_progress_summary(config.project_dir)

    # Main loop
    while True:
        state.iteration += 1

        # Check max iterations
        if config.max_iterations is not None and state.iteration > config.max_iterations:
            log(f"Reached max iterations ({config.max_iterations})", "LIMIT")
            print("To continue, run again without --max-iterations or with a higher value")
            break

        # Get model for this session
        model = get_model_for_session(state.session_type, config)

        # Print session header with timestamp
        print("\n" + "=" * 70)
        log(f"SESSION {state.iteration}: {state.session_type} ({model})", "SESSION")
        if state.current_feature:
            log(f"Feature: {state.current_feature}")
        if state.current_branch:
            log(f"Branch: {state.current_branch}")
        print("=" * 70 + "\n")

        # Get prompt for this session
        log("Generating prompt for session...")
        prompt = get_prompt_for_session(state.session_type, config, state)
        log(f"Prompt generated: {len(prompt)} characters")

        # Run session
        log("Invoking Claude Code CLI...")
        status, response = await run_agent_session(
            prompt=prompt,
            project_dir=config.project_dir,
            model=model,
            config=config,
        )
        log(f"Session returned with status: {status}")

        # Update state based on response
        # (In a more sophisticated version, we'd parse the response for status)

        # Determine next session type
        previous_type = state.session_type
        state.session_type = get_next_session_type(state, config)
        log(f"State transition: {previous_type} -> {state.session_type}")

        # Track feature completion
        if previous_type == SessionType.REVIEW and state.session_type == SessionType.IMPLEMENT:
            state.features_completed += 1
            state.current_feature = None
            state.current_branch = None
            log(f"Feature completed! Total: {state.features_completed}", "SUCCESS")

        # Save state
        state.save(config.project_dir)
        log("Session state saved")

        # Handle errors
        if status == "error":
            log("Session encountered an error, will retry...", "ERROR")
            state.session_type = previous_type  # Retry same session type

        # Progress summary
        print_progress_summary(config.project_dir)

        # Brief pause between sessions
        log("Preparing next session...")
        await asyncio.sleep(2)

    # Final summary
    print("\n" + "=" * 70)
    log("SESSION COMPLETE", "DONE")
    print("=" * 70)
    log(f"Project directory: {config.project_dir}")
    log(f"Features completed: {state.features_completed}")
    print_progress_summary(config.project_dir)
    log("Autonomous agent finished")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate spec file exists
    if not args.spec_file.exists():
        print(f"Error: Spec file not found: {args.spec_file}")
        return

    # Check for Claude Code CLI
    if not check_claude_code_installed():
        print("Error: Claude Code CLI not installed")
        print("\nInstall with: npm install -g @anthropic-ai/claude-code")
        return

    print("✓ Claude Code CLI installed")

    # Create config
    config = create_config_from_args(args)

    # Make paths absolute
    if not config.project_dir.is_absolute():
        config.project_dir = Path.cwd() / config.project_dir
    if not config.spec_file.is_absolute():
        config.spec_file = Path.cwd() / config.spec_file
    config.source_dirs = [
        Path.cwd() / p if not p.is_absolute() else p
        for p in config.source_dirs
    ]

    # Run the agent
    try:
        asyncio.run(run_autonomous_agent(config))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
