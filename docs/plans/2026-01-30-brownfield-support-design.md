# Brownfield Project Support Design

**Date:** 2026-01-30
**Status:** Approved

## Overview

Enable the autonomous coding system to work with existing projects by accepting freeform text input describing features and bugs, then appending these to an existing project's feature list without overwriting existing configuration or progress.

## Core Principles

1. **Freeform input** - Natural language descriptions, no structured format required
2. **Append-only** - Never overwrite existing project state
3. **Bugs first** - Bug fixes prioritized over new features
4. **Separate agents** - Dedicated BUGFIX agent instead of expanding IMPLEMENT
5. **Orchestrator decides** - Agent selection happens at orchestrator level, not agent level

---

## Input & CLI Changes

### New CLI Interface

```bash
# Brownfield mode - add to existing project
python autonomous_agent_demo.py \
    --input-file ./add_features.txt \
    --project-dir ./existing_project \
    --brownfield-model opus \
    --bugfix-model sonnet

# Greenfield mode - unchanged
python autonomous_agent_demo.py \
    --spec-file ./app_spec.txt \
    --project-dir ./new_project
```

### New CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--input-file` | - | Freeform text file (triggers brownfield mode) |
| `--brownfield-model` | opus | Model for brownfield initialization |
| `--bugfix-model` | sonnet | Model for bugfix sessions |

### Input File Format

Freeform natural language:

```
Add dark mode toggle to the settings page. Users should be
able to switch between light and dark themes.

The dashboard is loading slowly when there are more than
100 items. Need to add pagination or lazy loading.

Fix: Login button is unresponsive on mobile Safari. Users
report having to tap multiple times.
```

The BROWNFIELD_INITIALIZER agent classifies items using language cues:
- **Bug indicators:** "fix", "broken", "not working", "slow", "error", "crash", "issue"
- **Feature indicators:** "add", "create", "implement", "new", "support"

---

## Project Detection & Appspec Generation

### Detection Logic

```python
def detect_existing_project(project_dir: Path) -> bool:
    """Check if this is a brownfield project with existing state."""
    required_files = ["feature_list.json", "progress.json"]
    return all((project_dir / f).exists() for f in required_files)
```

### Appspec File Numbering

Each addition creates a new numbered appspec file:

```
existing_project/
├── app_spec.txt          # Original (001 implied)
├── app_spec_002.txt      # First addition
├── app_spec_003.txt      # Second addition
├── feature_list.json     # Accumulated entries
└── ...
```

### Files Preserved (Never Overwritten)

- `.agent_config.json`
- `.claude_settings.json`
- `CLAUDE.md`
- `progress.json` (appended to, not replaced)
- `reviews.json` (appended to, not replaced)
- `init.sh`

---

## Feature List Structure Changes

### Updated ID Scheme

- Features: `FEAT-001`, `FEAT-002`, etc.
- Bugs: `BUG-001`, `BUG-002`, etc.

### Updated Schema

```json
{
  "total_features": 52,
  "total_bugs": 3,
  "features": [
    {
      "id": "FEAT-001",
      "name": "User Authentication",
      "description": "...",
      "priority": 1,
      "category": "backend",
      "test_steps": ["..."],
      "passes": true,
      "source_appspec": "app_spec.txt"
    },
    {
      "id": "BUG-001",
      "name": "Login unresponsive on mobile Safari",
      "description": "Users report having to tap multiple times",
      "priority": 51,
      "category": "frontend",
      "type": "bug",
      "reproduction_steps": [
        "Open app on mobile Safari",
        "Navigate to login page",
        "Tap login button",
        "Observe: button requires multiple taps"
      ],
      "expected_behavior": "Single tap triggers login",
      "passes": false,
      "source_appspec": "app_spec_002.txt"
    }
  ]
}
```

### Key Differences for Bugs

| Field | Features | Bugs |
|-------|----------|------|
| `id` prefix | `FEAT-` | `BUG-` |
| `type` | (absent) | `"bug"` |
| Steps field | `test_steps` | `reproduction_steps` |
| Additional | - | `expected_behavior` |

---

## Priority & Ordering Logic

### Priority Order

1. Complete current in-progress work
2. Bugs from new input (BUG-XXX)
3. Remaining original features
4. New features (FEAT-XXX)

### Example

```
Existing features (incomplete):  FEAT-001 to FEAT-050
Current in-progress:             FEAT-023

New additions from input:
  - 2 bugs  → BUG-001, BUG-002
  - 3 features → FEAT-051, FEAT-052, FEAT-053

Resulting work order:
  1. FEAT-023 (finish in-progress)
  2. BUG-001
  3. BUG-002
  4. FEAT-024 to FEAT-050
  5. FEAT-051 to FEAT-053
```

---

## Agent Types

### Updated Agent Roster

| Agent | Model | Role |
|-------|-------|------|
| INITIALIZER | Sonnet | Greenfield - creates project from app_spec.txt |
| **BROWNFIELD_INITIALIZER** | **Opus** | Parses freeform input, appends to existing project |
| IMPLEMENT | Sonnet | Implements features (FEAT-XXX only) |
| **BUGFIX** | **Sonnet** | Reproduces and fixes bugs (BUG-XXX only) |
| REVIEW | Opus | Reviews implementations and bugfixes |
| FIX | Sonnet | Addresses review feedback |
| ARCHITECTURE | Opus | Periodic codebase health review |

---

## New Prompt Specifications

### Style Reference

**Both new prompts MUST follow the authoritarian style of existing prompts.**

Reference during implementation:
- `prompts/initializer_prompt.md` - For BROWNFIELD_INITIALIZER structure
- `prompts/coding_prompt.md` - For BUGFIX structure

Key style elements to replicate:
- `# YOUR ROLE - <AGENT_TYPE> AGENT` header
- `## STEP N:` numbered sections
- `DATA INTEGRITY - CATASTROPHIC REQUIREMENT` warnings
- Mandatory script usage tables
- DO/DON'T blocks with ✅ ⛔ symbols
- Session ending criteria

### 1. `brownfield_initializer_prompt.md`

**Based on:** `initializer_prompt.md`

**Key steps:**
1. Read freeform input file
2. Check existing project state via `features.py stats`
3. Classify items as BUG or FEAT using language cues
4. Create numbered `app_spec_XXX.txt`
5. Append entries via `features.py append`
6. Record session, commit, STOP (do not implement)

### 2. `bugfix_prompt.md`

**Based on:** `coding_prompt.md`

**Key steps:**
1. Get bearings, identify first pending BUG-XXX
2. Start servers
3. REPRODUCE bug using reproduction_steps (mandatory)
4. Investigate root cause
5. Create bugfix branch
6. Implement minimal fix
7. VERIFY fix using same reproduction_steps (mandatory)
8. Add regression test
9. Commit, record session, leave for REVIEW

---

## Script Changes (`scripts/features.py`)

### New Commands

```bash
# Append new entries
python scripts/features.py append --entries '[...]' --source-appspec app_spec_002.txt
```

### Updated `list` Output

Priority-ordered with clear sections:

```
=== IN PROGRESS ===
FEAT-023: User profile settings [in-progress]

=== BUGS (priority) ===
BUG-001: Login unresponsive on mobile Safari [pending]
BUG-002: Dashboard slow with 100+ items [pending]

=== FEATURES ===
FEAT-024: Email notifications [pending]
FEAT-025: Export to CSV [pending]
...

Summary: 1 in-progress, 2 bugs pending, 27 features pending
```

### Updated `stats` Output

```
Features: 45/50 passing
Bugs: 2/3 resolved
Next: BUG-002 (priority)
```

---

## State Machine Updates

### Orchestrator-Driven Agent Selection

The orchestrator (not the agent) checks feature_list.json and decides which agent to spawn:

```python
def get_next_work_session(project_dir: Path) -> SessionType:
    """Orchestrator checks feature_list and decides agent type."""
    feature_list = load_feature_list(project_dir)

    pending_bugs = [
        f for f in feature_list["features"]
        if f.get("type") == "bug" and not f["passes"]
    ]

    pending_features = [
        f for f in feature_list["features"]
        if not f.get("type") and not f["passes"]
    ]

    if pending_bugs:
        return SessionType.BUGFIX
    elif pending_features:
        return SessionType.IMPLEMENT
    else:
        return None  # All done
```

### Updated State Transitions

```
BROWNFIELD_INITIALIZER
    ↓ (appends entries to feature_list.json)
    ↓
Orchestrator checks feature_list
    ↓
    ├─ Pending bugs? → BUGFIX
    └─ No bugs? → IMPLEMENT
         ↓
       REVIEW
         ↓
         ├─ Issues? → FIX → REVIEW
         ├─ Architecture trigger? → ARCHITECTURE
         └─ Pass → Orchestrator checks again
              ↓
              ├─ More bugs? → BUGFIX
              └─ More features? → IMPLEMENT
```

### Brownfield Startup Sequence

```python
def determine_initial_session(config: AgentConfig, project_dir: Path) -> SessionType:
    has_existing = detect_existing_project(project_dir)

    if config.input_file:
        if not has_existing:
            raise ValueError("Brownfield mode requires existing project")
        return SessionType.BROWNFIELD_INITIALIZER

    elif config.spec_file:
        if has_existing:
            return load_resume_state(project_dir)
        else:
            return SessionType.INITIALIZER
```

---

## Config Changes

### Updated `config.py`

```python
@dataclass
class AgentConfig:
    # Existing fields...
    project_dir: Path
    spec_file: Path
    implement_model: str = "sonnet"
    review_model: str = "opus"
    fix_model: str = "sonnet"
    architecture_model: str = "opus"

    # New fields
    input_file: Optional[Path] = None
    brownfield_model: str = "opus"
    bugfix_model: str = "sonnet"


class SessionType(Enum):
    INITIALIZER = "INITIALIZER"
    BROWNFIELD_INITIALIZER = "BROWNFIELD_INITIALIZER"  # New
    IMPLEMENT = "IMPLEMENT"
    BUGFIX = "BUGFIX"  # New
    REVIEW = "REVIEW"
    FIX = "FIX"
    ARCHITECTURE = "ARCHITECTURE"
```

---

## Implementation Checklist

### Files to Create

- [ ] `prompts/brownfield_initializer_prompt.md`
- [ ] `prompts/bugfix_prompt.md`

### Files to Modify

- [ ] `config.py` - Add session types, config fields
- [ ] `autonomous_agent_demo.py` - Add CLI args, orchestrator logic
- [ ] `prompts.py` - Add prompt loading for new agents
- [ ] `scripts/features.py` - Add `append`, update `list` and `stats`

### Files Unchanged

- `prompts/coding_prompt.md` - Keep focused on features
- `prompts/initializer_prompt.md` - Keep for greenfield
- `prompts/reviewer_prompt.md` - Works for both
- `prompts/fix_prompt.md` - Works for both
