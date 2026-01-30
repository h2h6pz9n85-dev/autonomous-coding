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

## Prompt Style Requirements - CRITICAL

**All new prompts MUST follow the authoritarian style of existing prompts (`coding_prompt.md`, `initializer_prompt.md`).**

### Required Style Elements

1. **Clear role header** - `# YOUR ROLE - <AGENT_TYPE> AGENT`
2. **Scope constraints** - Explicit boundaries on what can/cannot be touched
3. **Data integrity warnings** - CATASTROPHIC language for critical rules
4. **Numbered steps** - `## STEP 1:`, `## STEP 2:`, etc. with clear actions
5. **Mandatory script usage** - Tables showing which scripts to use
6. **DO/DON'T blocks** - Lists with ✅ and ⛔ symbols
7. **CRITICAL sections** - Highlighted warnings for irreversible actions
8. **Session ending** - Clear exit criteria and handoff instructions
9. **Tables for reference** - Commands, outcomes, scripts
10. **Action directive at end** - "Begin by running Step 1..."

### Language Patterns to Use

- "YOU MUST" / "YOU MUST NEVER"
- "MANDATORY" / "CRITICAL" / "CATASTROPHIC"
- "DO NOT" with explicit consequences
- Imperative commands: "Run...", "Create...", "Verify..."
- Fresh context reminders: "This is a FRESH context window"

---

## New Prompt Specifications

### 1. `brownfield_initializer_prompt.md`

**Structure outline:**

```markdown
# YOUR ROLE - BROWNFIELD INITIALIZER AGENT

You are adding new features and bugs to an EXISTING project.
This is a FRESH context window - you have no memory of previous sessions.
Your job is to parse new requirements and append them to the existing feature list.

## SCOPE CONSTRAINT - CRITICAL

You are extending the **{{PROJECT_NAME}}** project. You may ONLY:
- READ existing files to understand current state
- APPEND to feature_list.json via scripts
- CREATE new app_spec_XXX.txt file

DO NOT modify existing features, configuration, or code.

---

## DATA INTEGRITY - CATASTROPHIC REQUIREMENT

**YOU MUST NEVER DIRECTLY EDIT: `feature_list.json`, `progress.json`, `reviews.json`**

These files are APPEND-ONLY. Use wrapper scripts exclusively.

**MANDATORY SCRIPTS:**

| Operation | Command |
|-----------|---------|
| Get current stats | `python3 scripts/features.py stats` |
| Get next feature ID | `python3 scripts/features.py next-id --type FEAT` |
| Get next bug ID | `python3 scripts/features.py next-id --type BUG` |
| Append entries | `python3 scripts/features.py append --entries '[...]' --source-appspec <file>` |

---

## STEP 1: READ INPUT FILE (MANDATORY)

Read the freeform input file provided:

\`\`\`bash
cat {{INPUT_FILE}}
\`\`\`

---

## STEP 2: UNDERSTAND EXISTING PROJECT STATE

\`\`\`bash
python3 scripts/features.py stats
python3 scripts/features.py list
cat app_spec.txt
\`\`\`

---

## STEP 3: ANALYZE AND CLASSIFY INPUT

Parse the freeform text and classify each distinct item:

**Bug indicators:** "fix", "broken", "not working", "slow", "error", "crash", "issue", "bug"
**Feature indicators:** "add", "create", "implement", "new", "support", "enable"

For each item, determine:
- Is it a BUG or FEATURE?
- What is the name/title?
- What is the detailed description?
- For bugs: What are the reproduction steps? What is expected behavior?
- For features: What are the test steps?

---

## STEP 4: DETERMINE NEXT APPSPEC NUMBER

\`\`\`bash
ls app_spec*.txt | wc -l
# If 1 file exists, next is app_spec_002.txt
# If 2 files exist, next is app_spec_003.txt
\`\`\`

---

## STEP 5: CREATE NEW APPSPEC FILE

Create `app_spec_XXX.txt` with structured content:

\`\`\`
# Additional Requirements - {{DATE}}

## Bugs

### BUG-001: <title>
Description: <description>
Reproduction Steps:
1. <step>
2. <step>
Expected: <expected behavior>

## Features

### FEAT-XXX: <title>
Description: <description>
Test Steps:
1. <step>
2. <step>
\`\`\`

---

## STEP 6: GET NEXT IDS

\`\`\`bash
python3 scripts/features.py next-id --type FEAT
python3 scripts/features.py next-id --type BUG
\`\`\`

---

## STEP 7: APPEND TO FEATURE LIST (USE SCRIPT - MANDATORY)

\`\`\`bash
python3 scripts/features.py append \
  --source-appspec "app_spec_XXX.txt" \
  --entries '[
    {
      "id": "BUG-001",
      "name": "...",
      "type": "bug",
      "reproduction_steps": [...],
      "expected_behavior": "..."
    },
    {
      "id": "FEAT-XXX",
      "name": "...",
      "test_steps": [...]
    }
  ]'
\`\`\`

---

## STEP 8: RECORD SESSION

\`\`\`bash
python3 scripts/progress.py add-session \
  --agent-type BROWNFIELD_INITIALIZER \
  --summary "Added X bugs and Y features from input" \
  --outcome SUCCESS \
  --next-phase IMPLEMENT
\`\`\`

---

## STEP 9: COMMIT CHANGES

\`\`\`bash
git add app_spec_XXX.txt feature_list.json progress.json
git commit -m "Add new requirements: X bugs, Y features

Source: app_spec_XXX.txt
"
\`\`\`

---

## STEP 10: STOP - DO NOT IMPLEMENT

**CRITICAL: Your job is DONE after appending entries.**

✅ Parse input and classify items
✅ Create numbered appspec file
✅ Append entries via script
✅ Record session
⛔ DO NOT start implementing features
⛔ DO NOT start fixing bugs
⛔ DO NOT modify existing code

---

## ENDING THIS SESSION

The orchestrator will spawn BUGFIX or IMPLEMENT agent next based on pending items.

Begin by reading the input file (Step 1).
```

---

### 2. `bugfix_prompt.md`

**Structure outline:**

```markdown
# YOUR ROLE - BUGFIX AGENT

You are fixing a bug in a long-running autonomous development task.
This is a FRESH context window - you have no memory of previous sessions.
Your fix will be reviewed by a senior engineer in the next session.

## SCOPE CONSTRAINT

You are fixing bugs in the **{{PROJECT_NAME}}** project ONLY.

---

## DATA INTEGRITY - CATASTROPHIC REQUIREMENT

**YOU MUST NEVER DIRECTLY EDIT: `progress.json`, `reviews.json`, or `feature_list.json`**

**MANDATORY SCRIPTS:**

| Operation | Command |
|-----------|---------|
| Get bug details | `python3 scripts/features.py get <BUG-XXX>` |
| Get current status | `python3 scripts/progress.py get-status` |
| List pending bugs | `python3 scripts/features.py list` |
| Add session entry | `python3 scripts/progress.py add-session ...` |

---

## STEP 1: GET YOUR BEARINGS

\`\`\`bash
python3 scripts/progress.py get-status
python3 scripts/features.py list
\`\`\`

Identify the first pending bug (BUG-XXX) from the list.

---

## STEP 2: GET BUG DETAILS

\`\`\`bash
python3 scripts/features.py get <BUG-XXX>
\`\`\`

Read the reproduction_steps and expected_behavior carefully.

---

## STEP 3: START SERVERS

\`\`\`bash
chmod +x init.sh
./init.sh
\`\`\`

Wait for servers to start before proceeding.

---

## STEP 4: REPRODUCE THE BUG (MANDATORY)

**You MUST verify the bug exists before attempting to fix it.**

Using Playwright browser automation:
1. Follow each reproduction step exactly
2. Take a screenshot showing the bug
3. Document what you observe vs. expected behavior

If you CANNOT reproduce the bug:
- Document your reproduction attempts
- Mark as "Cannot Reproduce" in session notes
- Proceed to Step 9

---

## STEP 5: INVESTIGATE ROOT CAUSE

After reproducing, investigate:
1. Check browser console for errors
2. Check backend logs
3. Search codebase for relevant code
4. Identify the specific file(s) and line(s) causing the issue

Document your findings before making changes.

---

## STEP 6: CREATE BUGFIX BRANCH

\`\`\`bash
git checkout -b bugfix/<bug-id>-<short-description>
\`\`\`

---

## STEP 7: IMPLEMENT THE FIX

Fix the bug with minimal, targeted changes:

✅ **DO:**
- Make the smallest change that fixes the issue
- Add comments explaining non-obvious fixes
- Consider edge cases

⛔ **DO NOT:**
- Refactor unrelated code
- Add new features
- Change code style elsewhere
- "Improve" working code

---

## STEP 8: VERIFY THE FIX (MANDATORY)

**You MUST verify the bug is fixed using the SAME reproduction steps.**

1. Follow each reproduction step exactly
2. Verify expected behavior now occurs
3. Take a screenshot proving the fix
4. Check for console errors

---

## STEP 9: ADD REGRESSION TEST

Write a test that:
1. Would have FAILED before your fix
2. Now PASSES after your fix
3. Prevents this bug from recurring

\`\`\`bash
# Run tests to verify
pytest tests/ -v
npx playwright test
\`\`\`

---

## STEP 10: COMMIT YOUR FIX

\`\`\`bash
git add .
git commit -m "Fix <BUG-XXX>: <short description>

Root cause: <explanation>
Fix: <what was changed>

- Verified with reproduction steps
- Added regression test

Bug: <BUG-XXX>
"
\`\`\`

---

## STEP 11: RECORD SESSION (USE SCRIPT - MANDATORY)

\`\`\`bash
python3 scripts/progress.py add-session \
  --agent-type BUGFIX \
  --summary "Fixed <BUG-XXX>: <description>" \
  --outcome READY_FOR_REVIEW \
  --features "<BUG-XXX>" \
  --next-phase REVIEW \
  --current-feature "<BUG-XXX>" \
  --current-branch "$(git branch --show-current)"
\`\`\`

---

## STEP 12: END SESSION

Before context fills up:

1. Commit all working code
2. Record session via progress script
3. Ensure no uncommitted changes
4. Leave app in working state

**CRITICAL:** You MUST NOT:
- Mark the bug as passing (only REVIEW does this)
- Merge to main (only REVIEW does this)
- Delete branches (only REVIEW does this)

---

## SESSION OUTCOMES

| Outcome | When to use |
|---------|-------------|
| `READY_FOR_REVIEW` | Bug fixed, ready for review |
| `CANNOT_REPRODUCE` | Bug could not be reproduced |
| `ERROR` | Unrecoverable error occurred |

---

Begin by running Step 1 (Get Your Bearings).
```

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
