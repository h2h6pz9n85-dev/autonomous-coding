# Autonomous Coding Agent

A reusable framework for long-running autonomous coding with Claude Code CLI. Implements a multi-agent pattern with distinct roles for implementation, code review, fixes, and architecture reviews.

**Adapted from [Anthropic's autonomous-coding quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding)** to use Claude Code CLI (included with Claude Max subscription).

## Key Features

- **Multi-Agent Workflow**: Different models for different tasks (Sonnet for coding, Opus for reviews)
- **Built-in Code Review**: Every implementation gets reviewed against a comprehensive checklist
- **Architecture Reviews**: Periodic codebase-wide reviews to prevent tech debt
- **Fully Configurable**: Apply to any project via CLI arguments
- **Resume Capability**: Pause and resume at any point

## Prerequisites

```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Login (uses your Claude Max subscription)
claude login

# Verify installation
claude --version
```

## Quick Start

```bash
# Minimal usage - just point to your spec file
python autonomous_agent_demo.py --spec-file ./my_app_spec.txt

# With custom project directory
python autonomous_agent_demo.py \
    --spec-file ./my_app_spec.txt \
    --project-dir ./generations/my_project

# Quick test run (3 iterations)
python autonomous_agent_demo.py \
    --spec-file ./my_app_spec.txt \
    --max-iterations 3
```

## Multi-Agent Workflow

The system uses five specialized agent roles:

| Role | Model | Purpose |
|------|-------|---------|
| **INITIALIZER** | Sonnet | Creates `feature_list.json` with testable features, sets up project |
| **IMPLEMENT** | Sonnet | Creates feature branches, implements features, writes tests |
| **REVIEW** | Opus | Reviews implementations against best practices checklist |
| **FIX** | Sonnet | Addresses issues found during code review |
| **ARCHITECTURE** | Opus | Periodic codebase-wide reviews (every N features) |

### Session Flow

```
INITIALIZER (first run only)
    ↓
IMPLEMENT → REVIEW ─┬─ (PASS) → merge → mark passing ─┐
    ↑               │                                  │
    │               ├─ (issues) → FIX → REVIEW ────────┤
    │               │                                  │
    │               └─ (REJECT) → delete branch ───────┤
    │                                                  │
    └──────────────────────────────────────────────────┘
    ↓
(every N features)
    ↓
ARCHITECTURE ─┬─ (PASS) → IMPLEMENT → ...
              │
              └─ (issues) → FIX → REVIEW → IMPLEMENT → ...
```

**Key rules (no exceptions):**

| Action | Who does it |
|--------|-------------|
| Mark `passes: true` | REVIEW only (after merging to main) |
| Merge to main | REVIEW only |
| Delete rejected branches | REVIEW only |
| Commit code changes | IMPLEMENT, FIX |
| Identify issues | REVIEW, ARCHITECTURE |

- FIX commits fixes but does NOT merge — REVIEW re-verifies and merges
- REJECT causes branch deletion and feature goes back to IMPLEMENT queue
- ARCHITECTURE identifies issues but does NOT fix them — FIX handles refactoring

### Architecture Review

Triggered every N completed features (default: 5). The architecture agent:

1. Analyzes codebase structure, code smells, SOLID violations
2. Scans for security issues (hardcoded secrets, injection vulnerabilities)
3. Checks test coverage
4. Writes findings to `reviews.json` (same format as code reviews)
5. Hands off to FIX agent if issues found (does NOT refactor directly)
6. Updates `progress.json` with session outcome

Health status: `GOOD` (no issues, >80% coverage), `FAIR` (no issues, 60-80% coverage), `NEEDS_ATTENTION` (issues present or <60% coverage).

## Command Line Options

```bash
python autonomous_agent_demo.py --help
```

| Option | Description | Default |
|--------|-------------|---------|
| `--spec-file` | Application specification file **(required)** | - |
| `--project-dir` | Directory for generated project | `./generations/project` |
| `--source-dir` | Additional source directories (can repeat) | `[]` |
| `--forbidden-dir` | Directories agent should NOT modify | `[]` |
| `--implement-model` | Model for implementation | `sonnet` |
| `--review-model` | Model for code review | `opus` |
| `--fix-model` | Model for fixing issues | `sonnet` |
| `--architecture-model` | Model for architecture reviews | `opus` |
| `--architecture-interval` | Run architecture review every N features | `5` |
| `--feature-count` | Number of features to generate | `50` |
| `--max-iterations` | Maximum agent iterations | Unlimited |
| `--main-branch` | Name of main git branch | `main` |
| `--config-file` | Load config from JSON file | - |

## Full Example

```bash
python autonomous_agent_demo.py \
    --spec-file ./app_spec.txt \
    --project-dir ./generations/my_saas \
    --source-dir ./shared \
    --source-dir ./lib \
    --forbidden-dir ./config \
    --implement-model sonnet \
    --review-model opus \
    --architecture-model opus \
    --architecture-interval 5 \
    --feature-count 30 \
    --max-iterations 50
```

## Code Review Checklist

Every implementation is reviewed against a comprehensive checklist covering:

- **SOLID Principles**: Single Responsibility, Open/Closed, Liskov Substitution, etc.
- **Code Smells**: God Class, Long Method, Feature Envy, Duplicate Code, etc.
- **Clean Code**: Meaningful names, small functions, proper error handling
- **Testing**: Positive/negative cases, edge cases, coverage
- **API Design**: RESTful principles, error responses, versioning
- **Security**: Input validation, authentication, injection prevention
- **Performance**: N+1 queries, caching, async operations

See `prompts/review_checklist.md` for the full checklist.

## Project Structure

```text
autonomous-coding/
├── autonomous_agent_demo.py  # Main entry point with CLI
├── config.py                 # Configuration dataclasses
├── agent.py                  # Claude Code CLI session logic
├── prompts.py                # Prompt generators for each session type
├── security.py               # Security settings and tool allowlist
├── progress.py               # Progress tracking utilities
├── prompts/
│   ├── schemas.md                    # Inter-agent JSON schemas
│   ├── review_checklist.md           # Code review checklist
│   ├── architecture_reviewer_prompt.md  # Architecture review agent
│   ├── initializer_prompt.md         # Project initialization
│   ├── coding_prompt.md              # Implementation agent
│   ├── reviewer_prompt.md            # Code review agent
│   └── fix_prompt.md                 # Fix agent
└── README.md
```

## Generated Project Structure

```text
your-project-dir/
├── feature_list.json           # Features with pass/fail status
├── progress.json               # Session history and project state
├── reviews.json                # All reviews (code + architecture) and fixes
├── app_spec.txt                # Copied specification
├── review_checklist.md         # Copied review checklist
├── CLAUDE.md                   # Project-specific rules
├── .agent_config.json          # Saved configuration for resume
├── .agent_state.json           # Saved session state for resume
└── [application files]         # Your generated application
```

## Resume Capability

The agent saves its state after each session. To resume:

```bash
# Simply run the same command again
python autonomous_agent_demo.py --spec-file ./app_spec.txt --project-dir ./generations/my_project
```

The agent will detect the existing project and continue from where it left off.

## Creating an App Specification

Create an `app_spec.txt` file describing your application:

```xml
<app_specification>
    <name>My Application</name>
    <description>Brief description of what the app does</description>

    <core_features>
        <feature>Feature 1 description</feature>
        <feature>Feature 2 description</feature>
    </core_features>

    <tech_stack>
        <frontend>React/Next.js/Vue/etc</frontend>
        <backend>FastAPI/Express/etc</backend>
        <database>PostgreSQL/MongoDB/etc</database>
    </tech_stack>

    <requirements>
        <requirement>Must be mobile responsive</requirement>
        <requirement>Must have authentication</requirement>
    </requirements>
</app_specification>
```

## Session Behavior

- **Initialization**: Generates feature list and project scaffolding. Duration depends on feature count.
- **Implementation**: One feature per session. Complexity varies by feature.
- **Review**: Reviews one feature branch per session.
- **Full build**: Duration scales with feature count and complexity.

## Troubleshooting

**"Agent appears to hang"**
This is normal during initialization. The agent is generating detailed test cases.

**"Not logged into Claude Code"**
Run `claude login` to authenticate with your Claude Max subscription.

**"Claude Code CLI not found"**
Install with: `npm install -g @anthropic-ai/claude-code`

**"Permission denied"**
Check that the project directory is writable and not in a forbidden directory.

## License

MIT License. Based on [Anthropic's autonomous-coding quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding).
