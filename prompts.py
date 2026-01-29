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


def copy_scripts_to_project(project_dir: Path) -> None:
    """Copy the scripts folder to the project directory.
    
    This ensures agents can access the scripts for managing 
    feature_list.json, progress.json, and reviews.json.
    """
    scripts_src = Path(__file__).parent / "scripts"
    scripts_dest = project_dir / "scripts"
    
    if not scripts_src.exists():
        print(f"Warning: Scripts folder not found: {scripts_src}")
        return
    
    if scripts_dest.exists():
        # Scripts already copied
        return
    
    # Copy entire scripts directory
    shutil.copytree(scripts_src, scripts_dest)
    print(f"Copied scripts/ folder to project directory")


def get_initializer_prompt(config: "AgentConfig") -> str:
    """Generate the initializer prompt for creating feature_list.json."""
    template = load_prompt_template("initializer_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
    })


def get_implement_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the implementation prompt."""
    template = load_prompt_template("coding_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
    })


def get_review_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the code review prompt."""
    template = load_prompt_template("reviewer_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "FEATURE_COUNT": str(config.feature_count),
        "MAIN_BRANCH": main_branch,
    })


def get_fix_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the fix prompt for addressing review issues."""
    template = load_prompt_template("fix_prompt")

    # Extract project name and path from config
    project_name = getattr(config, 'project_name', 'Project')
    project_path = getattr(config, 'project_path', 'products/app')
    main_branch = getattr(config, 'main_branch', 'main')

    return substitute_template(template, {
        "PROJECT_NAME": project_name,
        "PROJECT_PATH": project_path,
        "MAIN_BRANCH": main_branch,
    })


def get_architecture_prompt(config: "AgentConfig", state: "SessionState") -> str:
    """Generate the architecture review prompt."""
    template = load_prompt_template("architecture_reviewer_prompt")

    main_branch = getattr(config, 'main_branch', 'main')

    return substitute_template(template, {
        "ARCHITECTURE_INTERVAL": str(config.architecture_interval),
        "FEATURES_COMPLETED": str(state.features_completed),
        "MAIN_BRANCH": main_branch,
    })


