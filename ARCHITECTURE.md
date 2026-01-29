# Autonomous Coding Agent - Architecture Documentation

> Deep dive into the multi-agent orchestration system, agent communication patterns, and how agents understand their roles.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [How an Agent Knows Its Type](#how-an-agent-knows-its-type)
3. [Agent Orchestration Flow](#agent-orchestration-flow)
4. [Inter-Agent Communication](#inter-agent-communication)
5. [Session Lifecycle](#session-lifecycle)
6. [Key Design Patterns](#key-design-patterns)
7. [File Reference](#file-reference)

---

## System Overview

The autonomous coding agent is a **multi-agent orchestration system** that coordinates multiple AI agents to build software. Each agent runs in isolation with a fresh context window, communicating through structured JSON files.

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Python)                        │
│  autonomous_agent_demo.py                                       │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ config.py   │  │ prompts.py  │  │ agent.py                │ │
│  │             │  │             │  │                         │ │
│  │ State       │  │ Template    │  │ Claude Code CLI         │ │
│  │ Machine     │  │ Loading     │  │ Session Runner          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SHARED STATE (JSON Files)                    │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ progress.json   │  │ reviews.json    │  │ feature_list.   │ │
│  │                 │  │                 │  │ json            │ │
│  │ Session history │  │ Review cycles   │  │ Feature specs   │ │
│  │ Current state   │  │ Fix tracking    │  │ Pass/fail       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTS (Claude Code CLI)                     │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │INITIALIZER│ │IMPLEMENT │ │ REVIEW   │ │   FIX    │ │ ARCH  │ │
│  │          │ │          │ │          │ │          │ │       │ │
│  │ Sonnet   │ │ Sonnet   │ │ Opus     │ │ Sonnet   │ │ Opus  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Types and Models

| Agent | Model | Purpose |
|-------|-------|---------|
| **INITIALIZER** | Sonnet | Creates feature_list.json, sets up project |
| **IMPLEMENT** | Sonnet | Creates feature branches, implements features |
| **REVIEW** | Opus | Reviews code, merges to main, marks features passing |
| **FIX** | Sonnet | Addresses review issues |
| **ARCHITECTURE** | Opus | Periodic codebase-wide health reviews |

---

## How an Agent Knows Its Type

Agents are stateless Claude Code CLI sessions. They don't "remember" what type they are — they are **told explicitly** through three mechanisms:

### Agent Identity Discovery

```
┌─────────────────────────────────────────────────────────────────┐
│                     HOW AGENTS KNOW THEIR ROLE                  │
└─────────────────────────────────────────────────────────────────┘

     ┌──────────────────────────────────────────────────────┐
     │  1. PROMPT TEMPLATE DECLARATION                      │
     │                                                      │
     │  Each prompt file begins with explicit role:         │
     │                                                      │
     │  "# YOUR ROLE - IMPLEMENT AGENT"                     │
     │  "# YOUR ROLE - REVIEW AGENT"                        │
     │  etc.                                                │
     └──────────────────────────────────────────────────────┘
                              │
                              ▼
     ┌──────────────────────────────────────────────────────┐
     │  2. JSON CONTEXT FILES                               │
     │                                                      │
     │  progress.json provides:                             │
     │  - current_phase (what phase we're in)               │
     │  - current_feature (which feature to work on)        │
     │  - current_branch (active git branch)                │
     │  - features_completed (progress so far)              │
     └──────────────────────────────────────────────────────┘
                              │
                              ▼
     ┌──────────────────────────────────────────────────────┐
     │  3. SCOPE CONSTRAINTS (CLAUDE.md)                    │
     │                                                      │
     │  Project-specific rules about:                       │
     │  - Allowed directories                               │
     │  - Forbidden directories                             │
     │  - Permitted actions per role                        │
     └──────────────────────────────────────────────────────┘
```

### Prompt Template Mapping

| Agent Type | Prompt File | Implementation |
|------------|-------------|----------------|
| INITIALIZER | `prompts/initializer_prompt.md` | `prompts.py:get_initializer_prompt()` |
| IMPLEMENT | `prompts/coding_prompt.md` | `prompts.py:get_implement_prompt()` |
| REVIEW | `prompts/reviewer_prompt.md` | `prompts.py:get_review_prompt()` |
| FIX | `prompts/fix_prompt.md` | `prompts.py:get_fix_prompt()` |
| ARCHITECTURE | `prompts/architecture_reviewer_prompt.md` | `prompts.py:get_architecture_prompt()` |

### Prompt Loading Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────────────┐
│ config.py   │      │ prompts.py  │      │ Prompt Template     │
│             │      │             │      │ (.md file)          │
│ session_type├─────►│ load_prompt │      │                     │
│ "IMPLEMENT" │      │ _template() ├─────►│ # YOUR ROLE -       │
│             │      │             │      │   IMPLEMENT AGENT   │
└─────────────┘      │ substitute_ │      │                     │
                     │ template()  │      │ {{PROJECT_NAME}}    │
                     │             │      │ {{FEATURE_COUNT}}   │
                     └──────┬──────┘      └─────────────────────┘
                            │
                            ▼
                     ┌─────────────────────┐
                     │ Final Prompt        │
                     │                     │
                     │ Role declaration +  │
                     │ Project context +   │
                     │ Instructions        │
                     └─────────────────────┘
```

---

## Agent Orchestration Flow

### State Machine Diagram

```
                              ┌─────────────┐
                              │ INITIALIZER │
                              │             │
                              │ First run   │
                              │ only        │
                              └──────┬──────┘
                                     │
                                     ▼
              ┌─────────────────────────────────────────────┐
              │                                             │
              ▼                                             │
       ┌─────────────┐                                      │
       │  IMPLEMENT  │◄─────────────────────────────────────┤
       │             │                                      │
       │ Create      │                                      │
       │ branch,     │                                      │
       │ write code  │                                      │
       └──────┬──────┘                                      │
              │                                             │
              ▼                                             │
       ┌─────────────┐                                      │
       │   REVIEW    │                                      │
       │             │                                      │
       │ Evaluate    │                                      │
       │ code        │                                      │
       └──────┬──────┘                                      │
              │                                             │
              ├───────── PASS ──────────────────────────────┤
              │          (merge to main, mark passing)      │
              │                                             │
              ├───────── REQUEST_CHANGES ───┐               │
              │                             ▼               │
              │                      ┌─────────────┐        │
              │                      │     FIX     │        │
              │                      │             │        │
              │                      │ Address     │        │
              │                      │ issues      │        │
              │                      └──────┬──────┘        │
              │                             │               │
              │                             ▼               │
              │                      ┌─────────────┐        │
              │                      │   REVIEW    │        │
              │                      │ (re-verify) │        │
              │                      └──────┬──────┘        │
              │                             │               │
              │                             └─── PASS ──────┤
              │                                             │
              ├───────── REJECT ────────────────────────────┤
              │          (delete branch, retry)             │
              │                                             │
              └───────── ARCHITECTURE ──────────────────────┤
                         (every N features)                 │
                                │                           │
                                ▼                           │
                         ┌─────────────┐                    │
                         │ ARCHITECTURE│                    │
                         │             │                    │
                         │ Codebase    │                    │
                         │ health      │                    │
                         └──────┬──────┘                    │
                                │                           │
                                ├─── No issues ─────────────┘
                                │
                                └─── Issues ──► FIX ──► REVIEW
```

### State Transition Rules

| Current State | Condition | Next State |
|---------------|-----------|------------|
| INITIALIZER | Always | IMPLEMENT |
| IMPLEMENT | Always | REVIEW |
| REVIEW | Issues found | FIX |
| REVIEW | No issues + architecture trigger | ARCHITECTURE |
| REVIEW | No issues | IMPLEMENT (next feature) |
| FIX | Always | REVIEW (re-verify) |
| ARCHITECTURE | Always | IMPLEMENT |

**Implementation:** `config.py:get_next_session_type()`

### Architecture Review Trigger

```
                    features_completed
                           │
                           ▼
              ┌────────────────────────┐
              │                        │
              │  features_completed    │
              │  % architecture_       │──── remainder = 0 ───► ARCHITECTURE
              │  interval == 0 ?       │
              │                        │
              └────────────────────────┘
                           │
                    remainder != 0
                           │
                           ▼
                      IMPLEMENT
```

Default interval: Every 5 completed features.

---

## Inter-Agent Communication

Agents communicate **exclusively through structured JSON files**. There is no direct agent-to-agent messaging.

### Communication Flow

```
┌─────────────────┐                              ┌─────────────────┐
│   Session N     │                              │   Session N+1   │
│   (IMPLEMENT)   │                              │   (REVIEW)      │
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │  1. Read context                               │
         │         │                                      │
         │         ▼                                      │
         │  ┌─────────────────────────────────────┐      │
         │  │         JSON FILES                  │      │
         │  │                                     │      │
         │  │  progress.json ◄────────────────────┼──────┤ 4. Read
         │  │  feature_list.json                  │      │    context
         │  │  reviews.json                       │      │
         │  │                                     │      │
         │  └─────────────────────────────────────┘      │
         │         ▲                                      │
         │         │                                      │
         │  3. Write results                              │
         │  - session entry                               │
         │  - commits made                                │
         │  - outcome                                     │
         │                                                │
         │  2. Do work                                    │
         │  (implement feature)                           │
         │                                                │
         ▼                                                ▼
      [END]                                            [START]
```

### JSON Files Purpose

```
┌─────────────────────────────────────────────────────────────────┐
│                     JSON COMMUNICATION FILES                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  feature_list.json                                              │
│  ─────────────────                                              │
│  Created by: INITIALIZER                                        │
│  Read by: All agents                                            │
│  Contains: Feature specs, test steps, pass/fail status          │
│  Schema: prompts/schemas.md                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  progress.json                                                  │
│  ─────────────                                                  │
│  Created by: INITIALIZER                                        │
│  Updated by: All agents                                         │
│  Contains: Session history, current phase, feature progress     │
│  Schema: prompts/schemas.md                                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  reviews.json                                                   │
│  ────────────                                                   │
│  Created by: INITIALIZER (empty)                                │
│  Updated by: REVIEW, FIX, ARCHITECTURE                          │
│  Contains: Review findings, verdicts, fix tracking              │
│  Schema: prompts/schemas.md                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Handoff Example: IMPLEMENT → REVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│  IMPLEMENT writes to progress.json:                             │
│                                                                 │
│  sessions: [                                                    │
│    {                                                            │
│      session_id: 5,                                             │
│      agent_type: "IMPLEMENT",                                   │
│      features_touched: ["F003"],                                │
│      outcome: "READY_FOR_REVIEW",                               │
│      commit_range: { from: "abc123", to: "def456" }             │
│    }                                                            │
│  ]                                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  REVIEW reads progress.json, reviews commits, writes to         │
│  reviews.json:                                                  │
│                                                                 │
│  reviews: [                                                     │
│    {                                                            │
│      review_id: 3,                                              │
│      feature_id: "F003",                                        │
│      verdict: "REQUEST_CHANGES",                                │
│      issues: { major: [...] }                                   │
│    }                                                            │
│  ]                                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FIX reads reviews.json, fixes issues, writes to reviews.json:  │
│                                                                 │
│  fixes: [                                                       │
│    {                                                            │
│      fix_id: 1,                                                 │
│      review_id: 3,                                              │
│      issues_fixed: [...]                                        │
│    }                                                            │
│  ]                                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Session Lifecycle

### Complete Session Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│                                                                 │
│   1. Load state          ◄──── .agent_state.json                │
│   2. Determine session_type                                     │
│   3. Get model for session_type                                 │
│   4. Load prompt template                                       │
│   5. Substitute variables                                       │
│   6. Create security settings                                   │
│                                                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CLAUDE CODE CLI                            │
│                                                                 │
│   7. Receive prompt with role declaration                       │
│   8. Read JSON files for context                                │
│   9. Perform role-specific work                                 │
│  10. Update JSON files with results                             │
│  11. Commit changes to git                                      │
│  12. Session ends                                               │
│                                                                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
│                                                                 │
│  13. Parse session outcome                                      │
│  14. Calculate next session_type  ◄──── config.py               │
│  15. Update features_completed                                  │
│  16. Save state           ────► .agent_state.json               │
│  17. Loop back to step 1                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Model Selection

```
                    session_type
                         │
                         ▼
         ┌───────────────────────────────┐
         │                               │
         │  INITIALIZER ──────► Sonnet   │
         │  IMPLEMENT ────────► Sonnet   │
         │  REVIEW ───────────► Opus     │
         │  FIX ──────────────► Sonnet   │
         │  ARCHITECTURE ─────► Opus     │
         │                               │
         └───────────────────────────────┘

         Rationale:
         - Sonnet: Fast, capable (implementation)
         - Opus: Thorough, catches issues (review)
```

**Implementation:** `config.py:get_model_for_session()`

---

## Key Design Patterns

### 1. Separation of Concerns

```
┌─────────────────────────────────────────────────────────────────┐
│                  RESPONSIBILITY MATRIX                          │
└─────────────────────────────────────────────────────────────────┘

                    IMPLEMENT  REVIEW   FIX   ARCHITECTURE
                    ─────────  ──────   ───   ────────────
Create branch          ✓         -       ✓         -
Write code             ✓         -       ✓         -
Commit changes         ✓         -       ✓         -
Review code            -         ✓       -         ✓
Merge to main          ✗         ✓       ✗         ✗
Mark passing           ✗         ✓       ✗         -
Delete branch          -         ✓       -         -
Identify issues        -         ✓       -         ✓
Fix issues             -         -       ✓         -

✓ = Can do    ✗ = Explicitly forbidden    - = Not applicable
```

**Why:** Prevents agents from approving their own work.

### 2. Fresh Context Windows

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTEXT ISOLATION                           │
└─────────────────────────────────────────────────────────────────┘

     Session 1              Session 2              Session 3
     (IMPLEMENT)            (REVIEW)               (FIX)
         │                      │                      │
         ▼                      ▼                      ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐
    │  Fresh  │            │  Fresh  │            │  Fresh  │
    │ Context │            │ Context │            │ Context │
    │ Window  │            │ Window  │            │ Window  │
    └─────────┘            └─────────┘            └─────────┘
         │                      │                      │
         └──────────┬───────────┴───────────┬──────────┘
                    │                       │
                    ▼                       ▼
              ┌───────────────────────────────────┐
              │         JSON FILES                │
              │   (Shared state between agents)   │
              └───────────────────────────────────┘
```

**Why:** Prevents context window pollution, ensures deterministic behavior.

### 3. Deterministic State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                  DETERMINISTIC TRANSITIONS                      │
└─────────────────────────────────────────────────────────────────┘

Given:
  - current_session_type
  - review_issues (empty or not)
  - features_completed
  - architecture_interval

The next_session_type is ALWAYS predictable:
  - No randomness
  - No agent can skip states
  - No infinite loops possible
```

**Implementation:** `config.py:get_next_session_type()`

### 4. Resume Capability

```
┌─────────────────────────────────────────────────────────────────┐
│                     RESUME FLOW                                 │
└─────────────────────────────────────────────────────────────────┘

     First Run                              Resume
         │                                      │
         ▼                                      ▼
    ┌─────────┐                           ┌─────────┐
    │  Start  │                           │  Load   │
    │  Fresh  │                           │  State  │
    └────┬────┘                           └────┬────┘
         │                                     │
         ▼                                     │
    Run sessions                               │
         │                                     │
         ▼                                     │
    ┌─────────────────────┐                    │
    │ .agent_state.json   │◄───────────────────┘
    │ .agent_config.json  │
    │                     │
    │ - iteration         │
    │ - session_type      │
    │ - features_completed│
    └─────────────────────┘
```

**Resume command:** Same as original command.

### 5. Scope Isolation

```
┌─────────────────────────────────────────────────────────────────┐
│                   SECURITY BOUNDARIES                           │
└─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────┐
    │  ALLOWED                                                    │
    │  ────────                                                   │
    │  - Project directory                                        │
    │  - Configured source directories                            │
    │  - Git operations                                           │
    │  - Specified tools only                                     │
    └─────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────┐
    │  FORBIDDEN                                                  │
    │  ─────────                                                  │
    │  - Config directories                                       │
    │  - Other product directories                                │
    │  - System files                                             │
    └─────────────────────────────────────────────────────────────┘

Enforced via:
  - .claude_settings.json (tool permissions)
  - CLAUDE.md (project rules)
```

**Implementation:** `security.py:create_settings_file()`

---

## File Reference

### Orchestrator Files

| File | Purpose |
|------|---------|
| `autonomous_agent_demo.py` | Main entry point, CLI, main loop |
| `config.py` | AgentConfig, SessionState, state machine |
| `agent.py` | Claude Code CLI session execution |
| `prompts.py` | Prompt template loading |
| `security.py` | Security settings generation |
| `progress.py` | Progress tracking utilities |

### Prompt Files

| File | Agent Type |
|------|------------|
| `prompts/initializer_prompt.md` | INITIALIZER |
| `prompts/coding_prompt.md` | IMPLEMENT |
| `prompts/reviewer_prompt.md` | REVIEW |
| `prompts/fix_prompt.md` | FIX |
| `prompts/architecture_reviewer_prompt.md` | ARCHITECTURE |
| `prompts/schemas.md` | JSON schema documentation |
| `prompts/review_checklist.md` | Code review criteria |

### Generated Project Files

| File | Created By | Purpose |
|------|------------|---------|
| `feature_list.json` | INITIALIZER | Feature specifications |
| `progress.json` | All agents | Session history |
| `reviews.json` | REVIEW, FIX, ARCH | Review tracking |
| `.agent_state.json` | Orchestrator | Resume state |
| `.agent_config.json` | Orchestrator | Saved config |
| `CLAUDE.md` | Orchestrator | Project rules |
| `.claude_settings.json` | Orchestrator | Security settings |
