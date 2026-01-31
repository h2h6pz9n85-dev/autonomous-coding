"""
Prompt Generation
=================

Functions for generating prompts for each session type.
All prompts are loaded from markdown files in the prompts/ directory.
"""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import AgentConfig, SessionState


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt_template(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text()
    raise FileNotFoundError(f"Prompt template not found: {prompt_path}")


def substitute_template(template: str, substitutions: dict[str, str]) -> str:
    """Replace {{KEY}} placeholders in template with values from substitutions."""
    result = template
    for key, value in substitutions.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def copy_spec_to_project(spec_file: Path, project_dir: Path) -> None:
    """Copy the app spec file into the project directory."""
    if not spec_file.exists():
        print(f"Warning: Spec file not found: {spec_file}")
        return

    dest = project_file = project_dir / "app_spec.txt"
    if not dest.exists():
        shutil.copy(spec_file, dest)
        print(f"Copied {spec_file.name} to project directory")

    # Also copy the review checklist
    checklist_src = PROMPTS_DIR / "review_checklist.md"
    if checklist_src.exists():
        checklist_dest = project_dir / "review_checklist.md"
        if not checklist_dest.exists():
            shutil.copy(checklist_src, checklist_dest)
            print("Copied review_checklist.md to project directory")


def get_next_appspec_number(project_dir: Path) -> int:
    """Get the next appspec file number (for brownfield mode)."""
    import re
    existing = list(project_dir.glob("app_spec*.txt"))
    max_num = 1  # app_spec.txt is implicitly 001
    for f in existing:
        match = re.search(r'app_spec_(\d+)\.txt', f.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def copy_input_file_to_project(input_file: Path, project_dir: Path) -> Path:
    """Copy the freeform input file into the project directory.

    The file is copied as-is (not renamed to app_spec). The BROWNFIELD_INITIALIZER
    agent will read this file and transform it into a structured XML app_spec file.
    """
    if not input_file.exists():
        print(f"Warning: Input file not found: {input_file}")
        return None

    # Copy with original name - agent will transform it to XML app_spec format
    dest = project_dir / input_file.name
    shutil.copy(input_file, dest)
    print(f"Copied {input_file.name} to project directory")
    return dest


def copy_scripts_to_project(project_dir: Path) -> None:
    """Symlink the scripts folder to the project directory.

    This ensures agents can access the scripts for managing
    feature_list.json, progress.json, and reviews.json.
    Uses symlink so updates to scripts are immediately available.
    """
    scripts_src = Path(__file__).parent / "scripts"
    scripts_dest = project_dir / "scripts"

    if not scripts_src.exists():
        print(f"Warning: Scripts folder not found: {scripts_src}")
        return

    # If it's already a symlink pointing to the right place, skip
    if scripts_dest.is_symlink():
        if scripts_dest.resolve() == scripts_src.resolve():
            return
        # Wrong symlink target, remove it
        scripts_dest.unlink()
    elif scripts_dest.exists():
        # It's a regular directory (old copied version), remove it
        shutil.rmtree(scripts_dest)
        print(f"Removed old scripts/ folder, replacing with symlink")

    # Create symlink to the source scripts directory
    scripts_dest.symlink_to(scripts_src.resolve())
    print(f"Created scripts/ symlink -> {scripts_src.resolve()}")


def get_initializer_prompt(config: "AgentConfig") -> str:
    """Generate the initializer prompt for creating feature_list.json."""
    template = load_prompt_template("initializer_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_brownfield_initializer_prompt(config: "AgentConfig") -> str:
    """Generate the brownfield initializer prompt for appending to existing projects."""
    template = load_prompt_template("brownfield_initializer_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    # Use the original input file name (copied to project directory)
    input_file_name = config.input_file.name if config.input_file else "input.txt"

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "MAIN_BRANCH": main_branch,
        "INPUT_FILE": input_file_name,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_implement_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the implementation prompt."""
    template = load_prompt_template("coding_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_bugfix_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the bugfix prompt for fixing bugs (BUG-XXX entries)."""
    template = load_prompt_template("bugfix_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_review_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the code review prompt."""
    template = load_prompt_template("reviewer_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_fix_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the fix prompt for addressing review issues."""

    # If review_issues is empty, this is a Global Technical Debt Fix session
    # If review_issues has items, it's a standard Fix session for the current feature
    if not state.review_issues:
        template = load_prompt_template("global_fix_prompt")
    else:
        template = load_prompt_template("fix_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_architecture_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the architecture review prompt."""
    template = load_prompt_template("architecture_reviewer_prompt")

    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."

    return substitute_template(template, {
        "PROJECT_PATH": project_path,
        "ARCHITECTURE_INTERVAL": str(config.architecture_interval),
        "FEATURES_COMPLETED": str(state.features_completed),
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
    })


def get_global_fix_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the global tech debt fix prompt."""
    template = load_prompt_template("global_fix_prompt")

    main_branch = getattr(config, 'main_branch', 'main')
    agent_state_dir = str(config.agent_state_dir) if config.agent_state_dir else "."
    tech_debt_threshold = getattr(config, 'tech_debt_threshold', 5)

    return substitute_template(template, {
        "MAIN_BRANCH": main_branch,
        "AGENT_STATE_DIR": agent_state_dir,
        "TECH_DEBT_THRESHOLD": str(tech_debt_threshold),
    })


