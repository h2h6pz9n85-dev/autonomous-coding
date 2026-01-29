"""
Configuration Management
========================

Dataclasses and utilities for managing autonomous coding agent configuration.
All project-specific settings are passed via CLI or config file - no hardcoding.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json


@dataclass
class AgentConfig:
    """Configuration for the autonomous coding agent."""

    # Project paths
    project_dir: Path                          # Where generated code goes
    spec_file: Path                            # App specification file
    source_dirs: list[Path] = field(default_factory=list)  # Dirs agent can modify
    forbidden_dirs: list[Path] = field(default_factory=list)  # Dirs to avoid

    # Project identification (used in prompts)
    project_name: str = "Project"              # Human-readable project name
    project_path: str = "products/app"         # Path to main source code

    # Model configuration
    implement_model: str = "sonnet"            # Model for implementation
    review_model: str = "opus"                 # Model for code review
    fix_model: str = "sonnet"                  # Model for fixing review issues
    architecture_model: str = "opus"           # Model for architecture reviews

    # Session configuration
    max_iterations: Optional[int] = None       # Max total iterations
    architecture_interval: int = 5             # Run architecture review every N features
    feature_count: int = 50                    # Number of features to generate

    # Git configuration
    main_branch: str = "main"                  # Main branch name

    def __post_init__(self):
        """Convert paths to Path objects if strings."""
        if isinstance(self.project_dir, str):
            self.project_dir = Path(self.project_dir)
        if isinstance(self.spec_file, str):
            self.spec_file = Path(self.spec_file)
        self.source_dirs = [Path(p) if isinstance(p, str) else p for p in self.source_dirs]
        self.forbidden_dirs = [Path(p) if isinstance(p, str) else p for p in self.forbidden_dirs]

    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "project_dir": str(self.project_dir),
            "spec_file": str(self.spec_file),
            "source_dirs": [str(p) for p in self.source_dirs],
            "forbidden_dirs": [str(p) for p in self.forbidden_dirs],
            "project_name": self.project_name,
            "project_path": self.project_path,
            "implement_model": self.implement_model,
            "review_model": self.review_model,
            "fix_model": self.fix_model,
            "architecture_model": self.architecture_model,
            "max_iterations": self.max_iterations,
            "architecture_interval": self.architecture_interval,
            "feature_count": self.feature_count,
            "main_branch": self.main_branch,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        """Create config from dictionary."""
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save config to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "AgentConfig":
        """Load config from JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))


@dataclass
class SessionState:
    """Tracks the current state of the agent session."""

    iteration: int = 0
    features_completed: int = 0
    current_feature: Optional[str] = None
    current_branch: Optional[str] = None
    session_type: str = "INITIALIZER"  # INITIALIZER, IMPLEMENT, REVIEW, FIX, ARCHITECTURE
    review_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "features_completed": self.features_completed,
            "current_feature": self.current_feature,
            "current_branch": self.current_branch,
            "session_type": self.session_type,
            "review_issues": self.review_issues,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(**data)

    def save(self, project_dir: Path) -> None:
        """Save state to project directory."""
        state_file = project_dir / ".agent_state.json"
        with open(state_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, project_dir: Path) -> "SessionState":
        """Load state from project directory, or create new if not exists."""
        state_file = project_dir / ".agent_state.json"
        if state_file.exists():
            with open(state_file) as f:
                return cls.from_dict(json.load(f))
        return cls()


# Session type constants
class SessionType:
    INITIALIZER = "INITIALIZER"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    FIX = "FIX"
    ARCHITECTURE = "ARCHITECTURE"


def get_next_session_type(state: SessionState, config: AgentConfig) -> str:
    """
    Determine the next session type based on current state.

    Flow:
    1. INITIALIZER (first run only, creates feature_list.json)
    2. IMPLEMENT → REVIEW → FIX → (repeat for each feature)
    3. Every N features: ARCHITECTURE review
    """
    current = state.session_type

    if current == SessionType.INITIALIZER:
        return SessionType.IMPLEMENT

    if current == SessionType.IMPLEMENT:
        return SessionType.REVIEW

    if current == SessionType.REVIEW:
        # Check if review passed or needs fixes
        if state.review_issues:
            return SessionType.FIX
        else:
            # Review passed, check if architecture review needed
            if state.features_completed > 0 and state.features_completed % config.architecture_interval == 0:
                return SessionType.ARCHITECTURE
            return SessionType.IMPLEMENT

    if current == SessionType.FIX:
        # After fix, go back to review to verify
        return SessionType.REVIEW

    if current == SessionType.ARCHITECTURE:
        return SessionType.IMPLEMENT

    return SessionType.IMPLEMENT


def get_model_for_session(session_type: str, config: AgentConfig) -> str:
    """Get the appropriate model for a session type."""
    return {
        SessionType.INITIALIZER: config.implement_model,
        SessionType.IMPLEMENT: config.implement_model,
        SessionType.REVIEW: config.review_model,
        SessionType.FIX: config.fix_model,
        SessionType.ARCHITECTURE: config.architecture_model,
    }.get(session_type, config.implement_model)
