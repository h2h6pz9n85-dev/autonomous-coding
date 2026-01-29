# Inter-Agent Communication Schemas

> All agent communication MUST use these JSON structures.
> This enables reliable handoff between agents with fresh context windows.

---

## 1. Progress Tracking: `progress.json`

**Purpose:** Single source of truth for project state and session history.

```json
{
  "project": {
    "name": "Project Name",
    "created_at": "2025-01-29T10:00:00Z",
    "total_features": 50
  },
  "status": {
    "updated_at": "2025-01-29T14:30:00Z",
    "features_completed": 15,
    "features_passing": 12,
    "current_phase": "IMPLEMENT",
    "current_feature": "F016",
    "current_branch": "feature/user-authentication",
    "head_commit": "abc1234"
  },
  "sessions": [
    {
      "session_id": 1,
      "agent_type": "INITIALIZER",
      "started_at": "2025-01-29T10:00:00Z",
      "completed_at": "2025-01-29T10:45:00Z",
      "summary": "Created feature_list.json with 50 features, initialized git",
      "features_touched": [],
      "outcome": "SUCCESS",
      "commits": [
        {
          "hash": "a1b2c3d",
          "message": "Initial project setup"
        }
      ]
    },
    {
      "session_id": 2,
      "agent_type": "IMPLEMENT",
      "started_at": "2025-01-29T10:50:00Z",
      "completed_at": "2025-01-29T11:30:00Z",
      "summary": "Implemented F001 health check endpoint",
      "features_touched": ["F001"],
      "outcome": "READY_FOR_REVIEW",
      "commits": [
        {
          "hash": "d4e5f6g",
          "message": "Implement health check endpoint"
        },
        {
          "hash": "h7i8j9k",
          "message": "Add tests for health check"
        }
      ],
      "commit_range": {
        "from": "a1b2c3d",
        "to": "h7i8j9k"
      }
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project.name` | string | Human-readable project name |
| `project.created_at` | ISO 8601 | When project was initialized |
| `project.total_features` | int | Total features in feature_list.json |
| `status.updated_at` | ISO 8601 | Last update timestamp |
| `status.features_completed` | int | Features that passed review |
| `status.features_passing` | int | Features marked as passing |
| `status.current_phase` | enum | INITIALIZER, IMPLEMENT, REVIEW, FIX, ARCHITECTURE |
| `status.current_feature` | string | Feature ID being worked on (null if none) |
| `status.current_branch` | string | Git branch name (null if on main/master) |
| `status.head_commit` | string | Current HEAD commit hash (short) |
| `sessions[].session_id` | int | Sequential session number |
| `sessions[].agent_type` | enum | Agent that ran this session |
| `sessions[].started_at` | ISO 8601 | Session start time |
| `sessions[].completed_at` | ISO 8601 | Session end time |
| `sessions[].summary` | string | Brief description of work done |
| `sessions[].features_touched` | array | Feature IDs modified |
| `sessions[].outcome` | enum | SUCCESS, READY_FOR_REVIEW, NEEDS_FIX, ERROR |
| `sessions[].commits` | array | Commits made during this session (hash + message) |
| `sessions[].commit_range` | object | Range of commits (from, to) for this session's work |

---

## 2. Code Reviews: `reviews.json`

**Purpose:** Track all review cycles (both feature reviews and architecture reviews) with full history.

```json
{
  "schema_version": "1.0",
  "reviews": [
    {
      "review_id": 1,
      "feature_id": "F001",
      "feature_name": "Health Check Endpoint",
      "branch": "feature/health-check",
      "agent_type": "REVIEW",
      "timestamp": "2025-01-29T11:35:00Z",
      "commit_range": {
        "from": "a1b2c3d",
        "to": "h7i8j9k",
        "description": "Reviewing commits from main to feature branch HEAD"
      },
      "verdict": "REQUEST_CHANGES",
      "issues": {
        "critical": [],
        "major": [
          {
            "id": "R1-M1",
            "description": "Missing error handling for database connection failure",
            "location": "backend/app/routes/health.py:15",
            "suggestion": "Add try/except block with proper error response"
          }
        ],
        "minor": [],
        "suggestions": []
      },
      "checklist": {
        "functionality": "PASS",
        "security": "PASS",
        "testing": "FAIL",
        "code_quality": "PASS",
        "error_handling": "PASS",
        "maintainability": "PASS"
      },
      "summary": "Implementation is functional but missing error handling."
    },
    {
      "review_id": 2,
      "feature_id": null,
      "feature_name": "Architecture Review #1",
      "branch": null,
      "agent_type": "ARCHITECTURE",
      "timestamp": "2025-01-29T15:00:00Z",
      "trigger": "Every 5 features",
      "features_completed": 5,
      "verdict": "REQUEST_CHANGES",
      "health_status": "NEEDS_ATTENTION",
      "metrics": {
        "total_files": 45,
        "total_lines": 3200,
        "largest_file": {"path": "backend/app/services/processor.py", "lines": 280},
        "test_coverage_percent": 72
      },
      "issues": {
        "critical": [],
        "major": [
          {
            "id": "A2-M1",
            "description": "processor.py is a God class (280 lines)",
            "location": "backend/app/services/processor.py",
            "suggestion": "Extract validation logic into separate class"
          }
        ],
        "minor": [],
        "suggestions": []
      },
      "checklist": {
        "structure": "FAIL",
        "dependencies": "PASS",
        "security": "PASS",
        "testing": "PASS",
        "code_quality": "FAIL"
      },
      "summary": "Architecture review: NEEDS_ATTENTION. God class detected in processor.py."
    }
  ],
  "fixes": [
    {
      "fix_id": 1,
      "review_id": 1,
      "feature_id": "F001",
      "branch": "feature/health-check",
      "agent_type": "FIX",
      "timestamp": "2025-01-29T12:00:00Z",
      "issues_fixed": [
        {
          "issue_id": "R1-M1",
          "fix_description": "Added try/except with 503 response on DB failure",
          "commit": "abc123"
        }
      ],
      "issues_deferred": [],
      "tests_added": ["test_health_db_failure"],
      "merged_to_main": false,
      "pending_review": true
    },
    {
      "fix_id": 2,
      "review_id": 2,
      "feature_id": null,
      "branch": "refactor/arch-review-2",
      "agent_type": "FIX",
      "timestamp": "2025-01-29T16:00:00Z",
      "issues_fixed": [
        {
          "issue_id": "A2-M1",
          "fix_description": "Extracted ValidationService from processor.py",
          "commit": "def456"
        }
      ],
      "issues_deferred": [],
      "tests_added": [],
      "merged_to_main": false,
      "pending_review": true
    }
  ]
}
```

### Review Types

| agent_type | feature_id | branch | Purpose |
|------------|------------|--------|---------|
| `REVIEW` | Feature ID | feature/... | Code review for a specific feature |
| `ARCHITECTURE` | null | null | Periodic codebase health assessment |

### Review Verdicts

| Verdict | Meaning | Who Merges | Who Marks Passing |
|---------|---------|------------|-------------------|
| `PASS` | No issues | REVIEWER | REVIEWER |
| `PASS_WITH_COMMENTS` | Minor issues to address | REVIEWER (after re-verify) | REVIEWER (after re-verify) |
| `REQUEST_CHANGES` | Issues must be fixed | REVIEWER (after re-verify) | REVIEWER (after re-verify) |
| `REJECT` | Fundamental problems | Re-implement | N/A |

### Issue ID Format

**Feature Reviews:**
- `R{review_id}-C{n}` - Critical issue
- `R{review_id}-M{n}` - Major issue
- `R{review_id}-m{n}` - Minor issue
- `R{review_id}-S{n}` - Suggestion

**Architecture Reviews:**
- `A{review_id}-C{n}` - Critical issue (security, blocking)
- `A{review_id}-M{n}` - Major issue (God class, high complexity)
- `A{review_id}-m{n}` - Minor issue (style, small improvements)
- `A{review_id}-S{n}` - Suggestion

### Health Status (Architecture Reviews Only)

| Status | Criteria |
|--------|----------|
| `GOOD` | No critical/major issues, test coverage >80% |
| `FAIR` | No critical/major issues, coverage 60-80% |
| `NEEDS_ATTENTION` | Critical/major issues present OR coverage <60% |

---

## 4. Reading & Writing Conventions

### Reading JSON Files

**IMPORTANT: ALWAYS use wrapper scripts to read JSON files. NEVER execute direct Python code.**

```bash
# Get full status
python3 scripts/progress.py get-status

# Get specific field
python3 scripts/progress.py get-status --field current_branch
python3 scripts/progress.py get-status --field current_feature

# Get last session or specific field
python3 scripts/progress.py get-session -1
python3 scripts/progress.py get-session -1 --field agent_type
python3 scripts/progress.py get-session -1 --field commit_range.from

# Determine review type
python3 scripts/progress.py get-review-type

# Get last review or specific field
python3 scripts/reviews.py get-last
python3 scripts/reviews.py get-last --field review_id
python3 scripts/reviews.py get-last --field verdict

# Show issues from last review (formatted)
python3 scripts/reviews.py show-issues

# Feature operations
python3 scripts/features.py next
python3 scripts/features.py next-candidates  # Get up to 15 candidates to choose from
python3 scripts/features.py get F001
python3 scripts/features.py pass F001  # Single feature
python3 scripts/features.py pass-batch "F001,F002,F003"  # Multiple features
python3 scripts/features.py stats
```

**Check if file exists before reading:**

```bash
test -f progress.json && python3 scripts/progress.py get-status || echo "File not found"
```

### Timestamps

- Always use ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- Use UTC timezone (Z suffix)
- Get current timestamp: `date -u +"%Y-%m-%dT%H:%M:%SZ"`

### Session IDs

- Increment from the last session_id in progress.json
- If no sessions exist, start at 1

### Git Commit Tracking (MANDATORY)

**Every agent MUST record git commits in their JSON output.** This ensures:

- Clear audit trail of what was done
- Reviewers know exactly which commits to review
- Fix agents know which commits contain original vs fix code
- No scope creep - commit boundaries are explicit

**Getting commit information:**

```bash
# Get current HEAD commit (short hash)
git rev-parse --short HEAD

# Get main branch HEAD (replace 'main' with your branch name if different)
git rev-parse --short main  # or master, etc.

# List commits made during session (after starting commit)
git log --oneline <starting_commit>..HEAD

# Get commit with message
git log -1 --format="%h %s"
```

**Recording commits in sessions:**

```json
{
  "commits": [
    {"hash": "abc123", "message": "Implement health check endpoint"},
    {"hash": "def456", "message": "Add tests for health check"}
  ],
  "commit_range": {
    "from": "starting_commit_before_session",
    "to": "final_commit_of_session"
  }
}
```

**Recording commits in reviews:**

```json
{
  "commit_range": {
    "from": "main_branch_commit",
    "to": "feature_branch_head",
    "description": "Reviewing commits from main to feature HEAD"
  }
}
```

**The commit_range defines the EXACT scope of work:**

- **IMPLEMENT**: Records all commits made during implementation
- **REVIEW**: Records which commits are being reviewed (base..head)
- **FIX**: Records commits that address each issue

### Review Cycle Tracking

Each feature goes through review cycles:

1. IMPLEMENT creates code → records commits → outcome: READY_FOR_REVIEW
2. REVIEW reviews commit_range (main..feature_head) → verdict determines next step
3. If PASS: REVIEW merges to main, marks feature passing
4. If PASS_WITH_COMMENTS or REQUEST_CHANGES: FIX fixes issues → outcome: READY_FOR_REVIEW
5. REVIEW re-verifies fixes → if PASS: merges to main, marks feature passing
6. If REJECT: REVIEW deletes branch, feature goes back to IMPLEMENT queue

### Fix Cycle Limits

To prevent infinite loops, track fix attempts:

- **Max fix cycles**: 3 attempts per feature
- After 3 FIX attempts, decision is **severity-based**:
  - If only MINOR/SUGGESTION issues remain → **PASS_WITH_COMMENTS** (merge with documented tech debt)
  - If CRITICAL/MAJOR issues still remain → **REJECT** (fundamental problems, re-implement)
- Track via counting `fixes` entries with same `feature_id` in reviews.json

```bash
# Count fix attempts for current feature (use wrapper script)
python3 scripts/reviews.py get-fix-count <FEATURE_ID>
```

Output shows:
- `FIX_COUNT: N` - Number of fix attempts
- `REMAINING: M` - Remaining attempts (3 - N)
- Warning if final attempt
- Error if max attempts reached

**Linking reviews and fixes:**

- `fix.review_id` references which review the fix addresses
- `fix.issues_fixed[].commit` records which commit fixed each issue
- `fix.merge_commit` records the final merge to main

---

## 5. Agent Responsibilities Matrix

**CRITICAL: Only REVIEW can merge to main and mark features as passing.**

| Action | IMPLEMENT | REVIEW | FIX | ARCHITECTURE |
|--------|-----------|--------|-----|--------------|
| Create feature branch | ✓ | - | ✓ (refactor branch) | - |
| Implement code | ✓ | - | ✓ (fixes only) | - |
| Mark `passes: false` | ✓ (regressions) | - | - | - |
| **Mark `passes: true`** | ✗ NEVER | **✓ ONLY** | ✗ NEVER | - |
| **Merge to main** | ✗ NEVER | **✓ ONLY** | ✗ NEVER | ✗ NEVER |
| Delete feature branch | ✗ | ✓ (REJECT or after merge) | ✗ | - |
| Write to reviews.json | - | ✓ (reviews) | ✓ (fixes) | ✓ (reviews) |

**Why this matters:**
- IMPLEMENT creates code but cannot verify its own work
- FIX addresses issues but cannot approve its own fixes
- ARCHITECTURE identifies issues but cannot fix its own findings
- REVIEW is the sole gatekeeper — nothing reaches main without REVIEW approval
- This prevents agents from marking their own work as complete

---

## 6. Session Outcomes

| Outcome | Used By | Meaning |
|---------|---------|---------|
| `SUCCESS` | INITIALIZER, REVIEW (PASS), ARCHITECTURE | Task completed successfully |
| `READY_FOR_REVIEW` | IMPLEMENT, FIX | Code ready for (re-)review |
| `NEEDS_FIX` | REVIEW (REQUEST_CHANGES, PASS_WITH_COMMENTS) | Issues need to be addressed |
| `REJECTED` | REVIEW (REJECT verdict) | Fundamental problems, needs re-implementation |
| `ERROR` | Any | Unrecoverable error occurred |

> **Note on `current_phase`:** After a session completes, `current_phase` should indicate the **next** agent type that will run. For example, IMPLEMENT sets `current_phase: "REVIEW"` when outcome is `READY_FOR_REVIEW`.
