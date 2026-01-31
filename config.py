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


def detect_existing_project(agent_state_dir: Path) -> bool:
    """Check if this is a brownfield project with existing state."""
    required_files = ["feature_list.json", "progress.json"]
    return all((agent_state_dir / f).exists() for f in required_files)


@dataclass
class AgentConfig:
    """Configuration for the autonomous coding agent."""

    # Project paths
    project_dir: Path                          # Where generated code goes
    agent_state_dir: Optional[Path] = None     # Where agent state files go (defaults to project_dir)
    spec_file: Optional[Path] = None           # App specification file (greenfield)
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

    # Brownfield configuration
    input_file: Optional[Path] = None          # Freeform input file (brownfield mode)
    brownfield_model: str = "opus"             # Model for brownfield initialization
    bugfix_model: str = "sonnet"               # Model for bugfix sessions
    global_fix_model: str = "sonnet"           # Model for global tech debt fix sessions
    tech_debt_threshold: int = 5               # Trigger GLOBAL_FIX when tech debt count >= threshold

    # Resume mode (skip initialization, continue from saved state)
    resume_mode: bool = False

    def __post_init__(self):
        """Convert paths to Path objects if strings."""
        if isinstance(self.project_dir, str):
            self.project_dir = Path(self.project_dir)
        if self.agent_state_dir is not None and isinstance(self.agent_state_dir, str):
            self.agent_state_dir = Path(self.agent_state_dir)
        # Default agent_state_dir to project_dir if not specified
        if self.agent_state_dir is None:
            self.agent_state_dir = self.project_dir
        if self.spec_file is not None and isinstance(self.spec_file, str):
            self.spec_file = Path(self.spec_file)
        if self.input_file is not None and isinstance(self.input_file, str):
            self.input_file = Path(self.input_file)
        self.source_dirs = [Path(p) if isinstance(p, str) else p for p in self.source_dirs]
        self.forbidden_dirs = [Path(p) if isinstance(p, str) else p for p in self.forbidden_dirs]

    # Path helper methods for agent state files
    def get_progress_json_path(self) -> Path:
        """Path to progress.json in agent state directory."""
        return self.agent_state_dir / "progress.json"

    def get_feature_list_path(self) -> Path:
        """Path to feature_list.json in agent state directory."""
        return self.agent_state_dir / "feature_list.json"

    def get_reviews_json_path(self) -> Path:
        """Path to reviews.json in agent state directory."""
        return self.agent_state_dir / "reviews.json"

    def get_console_dir(self) -> Path:
        """Path to console output directory."""
        return self.agent_state_dir / "console"

    def get_progress_dir(self) -> Path:
        """Path to progress summaries directory."""
        return self.agent_state_dir / "progress"

    def get_backups_dir(self) -> Path:
        """Path to backups directory."""
        return self.agent_state_dir / ".backups"

    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "project_dir": str(self.project_dir),
            "agent_state_dir": str(self.agent_state_dir) if self.agent_state_dir else None,
            "spec_file": str(self.spec_file) if self.spec_file else None,
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
            "input_file": str(self.input_file) if self.input_file else None,
            "brownfield_model": self.brownfield_model,
            "bugfix_model": self.bugfix_model,
            "global_fix_model": self.global_fix_model,
            "tech_debt_threshold": self.tech_debt_threshold,
            "resume_mode": self.resume_mode,
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
    total_implementations: int = 0
    last_global_fix_implementation_count: int = 0

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "features_completed": self.features_completed,
            "current_feature": self.current_feature,
            "current_branch": self.current_branch,
            "session_type": self.session_type,
            "review_issues": self.review_issues,
            "total_implementations": self.total_implementations,
            "last_global_fix_implementation_count": self.last_global_fix_implementation_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(**data)

    def save(self, state_dir: Path) -> None:
        """Save state to agent state directory."""
        state_file = state_dir / ".agent_state.json"
        with open(state_file, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, state_dir: Path) -> "SessionState":
        """Load state from agent state directory, or create new if not exists."""
        state_file = state_dir / ".agent_state.json"
        if state_file.exists():
            with open(state_file) as f:
                return cls.from_dict(json.load(f))
        return cls()


# Session type constants
class SessionType:
    INITIALIZER = "INITIALIZER"
    BROWNFIELD_INITIALIZER = "BROWNFIELD_INITIALIZER"
    IMPLEMENT = "IMPLEMENT"
    BUGFIX = "BUGFIX"
    REVIEW = "REVIEW"
    FIX = "FIX"
    ARCHITECTURE = "ARCHITECTURE"
    GLOBAL_FIX = "GLOBAL_FIX"


def get_next_work_session(agent_state_dir: Path, tech_debt_threshold: int = 5) -> str:
    """
    Orchestrator checks feature_list and decides agent type.

    Priority order:
    1. Bugs (BUG-XXX) - always first
    2. Tech debt (DEBT-XXX) - if accumulated >= threshold, trigger GLOBAL_FIX
    3. Features (FEAT-XXX)

    Returns SessionType.BUGFIX, SessionType.GLOBAL_FIX, SessionType.IMPLEMENT, or None if all done.
    """
    feature_list_path = agent_state_dir / "feature_list.json"
    if not feature_list_path.exists():
        return SessionType.IMPLEMENT

    with open(feature_list_path) as f:
        data = json.load(f)

    features = data.get("features", [])

    # Check for pending bugs first (bugs have highest priority)
    pending_bugs = [
        f for f in features
        if f.get("type") == "bug" and not f.get("passes", False)
    ]

    if pending_bugs:
        return SessionType.BUGFIX

    # Check for accumulated tech debt (threshold check)
    pending_debt = [
        f for f in features
        if f.get("type") == "tech_debt" and not f.get("passes", False)
    ]

    if len(pending_debt) >= tech_debt_threshold:
        return SessionType.GLOBAL_FIX

    # Check for pending features
    pending_features = [
        f for f in features
        if f.get("type") not in ("bug", "tech_debt") and not f.get("passes", False)
    ]

    if pending_features:
        return SessionType.IMPLEMENT

    # If only tech debt remains (below threshold), still work on it
    if pending_debt:
        return SessionType.GLOBAL_FIX

    return None  # All done


def get_pending_tech_debt_count(agent_state_dir: Path) -> int:
    """Get the count of pending tech debt items."""
    feature_list_path = agent_state_dir / "feature_list.json"
    if not feature_list_path.exists():
        return 0

    with open(feature_list_path) as f:
        data = json.load(f)

    features = data.get("features", [])
    return sum(
        1 for f in features
        if f.get("type") == "tech_debt" and not f.get("passes", False)
    )


def get_next_session_type(state: SessionState, config: AgentConfig) -> str:
    """
    Determine the next session type based on current state.

    Flow:
    1. INITIALIZER (first run only, creates feature_list.json)
    2. BROWNFIELD_INITIALIZER (brownfield mode, appends to existing project)
    3. IMPLEMENT → REVIEW → FIX → (repeat for each feature)
    4. Every N features: ARCHITECTURE review
    5. When tech debt >= threshold: GLOBAL_FIX

    Priority: BUGS > TECH_DEBT (if >= threshold) > FEATURES > ARCHITECTURE
    """
    current = state.session_type

    if current == SessionType.INITIALIZER:
        return SessionType.IMPLEMENT

    if current == SessionType.BROWNFIELD_INITIALIZER:
        return SessionType.IMPLEMENT

    if current == SessionType.IMPLEMENT:
        return SessionType.REVIEW

    if current == SessionType.BUGFIX:
        return SessionType.REVIEW

    if current == SessionType.REVIEW:
        # Check if review passed or needs fixes
        if state.review_issues:
            return SessionType.FIX
        else:
            # Review passed. Check what to do next.

            # Check for accumulated tech debt (priority over architecture review)
            debt_count = get_pending_tech_debt_count(config.agent_state_dir)
            if debt_count >= config.tech_debt_threshold:
                return SessionType.GLOBAL_FIX

            # Check if architecture review needed
            if state.features_completed > 0 and state.features_completed % config.architecture_interval == 0:
                return SessionType.ARCHITECTURE

            return SessionType.IMPLEMENT

    if current == SessionType.FIX:
        # After fix, go back to review to verify
        return SessionType.REVIEW

    if current == SessionType.GLOBAL_FIX:
        # After global fix, go back to implement (no review needed for tech debt)
        return SessionType.IMPLEMENT

    if current == SessionType.ARCHITECTURE:
        return SessionType.IMPLEMENT

    return SessionType.IMPLEMENT


def get_model_for_session(session_type: str, config: AgentConfig) -> str:
    """Get the appropriate model for a session type."""
    return {
        SessionType.INITIALIZER: config.implement_model,
        SessionType.BROWNFIELD_INITIALIZER: config.brownfield_model,
        SessionType.IMPLEMENT: config.implement_model,
        SessionType.BUGFIX: config.bugfix_model,
        SessionType.REVIEW: config.review_model,
        SessionType.FIX: config.fix_model,
        SessionType.ARCHITECTURE: config.architecture_model,
        SessionType.GLOBAL_FIX: config.global_fix_model,
    }.get(session_type, config.implement_model)
