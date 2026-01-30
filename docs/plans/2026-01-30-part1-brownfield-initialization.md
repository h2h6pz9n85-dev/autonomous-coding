# Part 1: Brownfield Initialization

**Date:** 2026-01-30
**Status:** Approved
**Depends on:** Nothing (implement first)

## Overview

Enable the autonomous coding system to accept freeform text input describing features and bugs, parse it, and append entries to an existing project's feature list without overwriting existing state.

---

## Input & CLI Changes

### New CLI Arguments

```bash
python autonomous_agent_demo.py \
    --input-file ./add_features.txt \
    --project-dir ./existing_project \
    --brownfield-model opus
```

| Argument | Default | Description |
| -------- | ------- | ----------- |
| `--input-file` | - | Freeform text file (triggers brownfield mode) |
| `--brownfield-model` | opus | Model for brownfield initialization |

### Input File Format

Freeform natural language:

```text
Add dark mode toggle to the settings page. Users should be
able to switch between light and dark themes.

The dashboard is loading slowly when there are more than
100 items. Need to add pagination or lazy loading.

Fix: Login button is unresponsive on mobile Safari. Users
report having to tap multiple times.
```

Classification cues:

- **Bug indicators:** "fix", "broken", "not working", "slow", "error", "crash", "issue"
- **Feature indicators:** "add", "create", "implement", "new", "support"

---

## Project Detection

```python
def detect_existing_project(project_dir: Path) -> bool:
    """Check if this is a brownfield project with existing state."""
    required_files = ["feature_list.json", "progress.json"]
    return all((project_dir / f).exists() for f in required_files)
```

### Files Preserved (Never Overwritten)

- `.agent_config.json`
- `.claude_settings.json`
- `CLAUDE.md`
- `progress.json` (appended to, not replaced)
- `reviews.json` (appended to, not replaced)
- `init.sh`

---

## Appspec File Numbering

Each addition creates a new numbered appspec file:

```text
existing_project/
├── app_spec.txt          # Original (001 implied)
├── app_spec_002.txt      # First addition
├── app_spec_003.txt      # Second addition
├── feature_list.json     # Accumulated entries
└── ...
```

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
| ----- | -------- | ---- |
| `id` prefix | `FEAT-` | `BUG-` |
| `type` | (absent) | `"bug"` |
| Steps field | `test_steps` | `reproduction_steps` |
| Additional | - | `expected_behavior` |

---

## New Agent: BROWNFIELD_INITIALIZER

| Agent | Model | Role |
| ----- | ----- | ---- |
| BROWNFIELD_INITIALIZER | Opus | Parses freeform input, appends to existing project |

### Prompt: `brownfield_initializer_prompt.md`

**Based on:** `prompts/initializer_prompt.md`

**Key steps:**

1. Read freeform input file
2. Check existing project state via `features.py stats`
3. Classify items as BUG or FEAT using language cues
4. Create numbered `app_spec_XXX.txt`
5. Append entries via `features.py append`
6. Record session, commit, STOP (do not implement)

---

## Script Changes (`scripts/features.py`)

### New Command: `append`

```bash
python scripts/features.py append --entries '[...]' --source-appspec app_spec_002.txt
```

### New Command: `next-id`

```bash
python scripts/features.py next-id --type FEAT  # Returns FEAT-051
python scripts/features.py next-id --type BUG   # Returns BUG-001
```

---

## Config Changes

### Updated `config.py`

```python
@dataclass
class AgentConfig:
    # Existing fields...

    # New fields
    input_file: Optional[Path] = None
    brownfield_model: str = "opus"


class SessionType(Enum):
    INITIALIZER = "INITIALIZER"
    BROWNFIELD_INITIALIZER = "BROWNFIELD_INITIALIZER"  # New
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    FIX = "FIX"
    ARCHITECTURE = "ARCHITECTURE"
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

## Implementation Checklist

### Files to Create

- [ ] `prompts/brownfield_initializer_prompt.md`

### Files to Modify

- [ ] `config.py` - Add `BROWNFIELD_INITIALIZER` session type, `input_file`, `brownfield_model` fields
- [ ] `autonomous_agent_demo.py` - Add `--input-file`, `--brownfield-model` CLI args, brownfield startup logic
- [ ] `prompts.py` - Add prompt loading for BROWNFIELD_INITIALIZER
- [ ] `scripts/features.py` - Add `append` and `next-id` commands
