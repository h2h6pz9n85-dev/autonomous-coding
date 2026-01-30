# Part 2: Bugfix Agent

**Date:** 2026-01-30
**Status:** Approved
**Depends on:** Part 1 (Brownfield Initialization)

## Overview

Add a dedicated BUGFIX agent that reproduces, fixes, and verifies bugs. The orchestrator prioritizes bugs over features and spawns the appropriate agent.

---

## CLI Changes

### New CLI Argument

```bash
python autonomous_agent_demo.py \
    --bugfix-model sonnet
```

| Argument | Default | Description |
| -------- | ------- | ----------- |
| `--bugfix-model` | sonnet | Model for bugfix sessions |

---

## Priority & Ordering Logic

### Priority Order

1. Complete current in-progress work
2. Bugs (BUG-XXX) - always before new features
3. Remaining features (FEAT-XXX)

### Example

```text
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

## New Agent: BUGFIX

| Agent | Model | Role |
| ----- | ----- | ---- |
| BUGFIX | Sonnet | Reproduces and fixes bugs (BUG-XXX only) |

### Prompt: `bugfix_prompt.md`

**Based on:** `prompts/coding_prompt.md`

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

## Orchestrator-Driven Agent Selection

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

---

## State Machine Updates

### Updated State Transitions

```text
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

---

## Script Changes (`scripts/features.py`)

### Updated `list` Output

Priority-ordered with clear sections:

```text
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

```text
Features: 45/50 passing
Bugs: 2/3 resolved
Next: BUG-002 (priority)
```

---

## Config Changes

### Updated `config.py`

```python
@dataclass
class AgentConfig:
    # Existing fields...

    # New field
    bugfix_model: str = "sonnet"


class SessionType(Enum):
    INITIALIZER = "INITIALIZER"
    BROWNFIELD_INITIALIZER = "BROWNFIELD_INITIALIZER"
    IMPLEMENT = "IMPLEMENT"
    BUGFIX = "BUGFIX"  # New
    REVIEW = "REVIEW"
    FIX = "FIX"
    ARCHITECTURE = "ARCHITECTURE"
```

---

## Implementation Checklist

### Files to Create

- [ ] `prompts/bugfix_prompt.md`

### Files to Modify

- [ ] `config.py` - Add `BUGFIX` session type, `bugfix_model` field
- [ ] `autonomous_agent_demo.py` - Add `--bugfix-model` CLI arg, orchestrator agent selection logic
- [ ] `prompts.py` - Add prompt loading for BUGFIX
- [ ] `scripts/features.py` - Update `list` to show priority sections, update `stats` for bug counts
