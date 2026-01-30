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

## Implementation Parts

This design is split into two parts for separate implementation:

### Part 1: Brownfield Initialization

**File:** [2026-01-30-part1-brownfield-initialization.md](2026-01-30-part1-brownfield-initialization.md)

**Scope:**

- `--input-file` and `--brownfield-model` CLI arguments
- Project detection logic
- Appspec file numbering (app_spec_002.txt, etc.)
- Feature list structure changes (FEAT-XXX, BUG-XXX IDs)
- BROWNFIELD_INITIALIZER agent and prompt
- `features.py append` and `next-id` commands

**Implement first** - no dependencies.

### Part 2: Bugfix Agent

**File:** [2026-01-30-part2-bugfix-agent.md](2026-01-30-part2-bugfix-agent.md)

**Scope:**

- `--bugfix-model` CLI argument
- BUGFIX agent and prompt
- Priority/ordering logic (bugs before features)
- Orchestrator-driven agent selection
- `features.py list` with priority sections
- State machine updates for BUGFIX → REVIEW flow

**Implement second** - depends on Part 1 for feature list structure.

---

## Prompt Style Reference

Both new prompts MUST follow the authoritarian style of existing prompts.

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

---

## Agent Summary

| Agent | Model | Role |
| ----- | ----- | ---- |
| INITIALIZER | Sonnet | Greenfield - creates project from app_spec.txt |
| **BROWNFIELD_INITIALIZER** | **Opus** | Parses freeform input, appends to existing project |
| IMPLEMENT | Sonnet | Implements features (FEAT-XXX only) |
| **BUGFIX** | **Sonnet** | Reproduces and fixes bugs (BUG-XXX only) |
| REVIEW | Opus | Reviews implementations and bugfixes |
| FIX | Sonnet | Addresses review feedback |
| ARCHITECTURE | Opus | Periodic codebase health review |
