# Verification Evidence System Design

> Explicit verification artifacts with subagent-based verification and adversarial review process to eliminate self-verification bias in autonomous coding agents.

---

## Overview

Current system weakness: **implementers verify their own work**. The coder takes screenshots, checks tests, and claims "READY_FOR_REVIEW" based on self-generated evidence. This creates confirmation bias.

**Solution:**
1. **Verification artifacts** — Explicit folder structure with documented evidence
2. **Subagent verification** — Independent agent creates verification report (fresh context, no implementation knowledge)
3. **Adversarial review** — Reviewer assumes feature is broken and attempts to prove it

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           IMPLEMENT SESSION                                  │
│                                                                              │
│   1. Implement feature (write code, tests)                                   │
│   2. Commit changes                                                          │
│   3. Spawn VERIFICATION SUBAGENT ─────────────────────────────┐              │
│      │                                                        │              │
│      │  Subagent receives ONLY:                               │              │
│      │  - Feature specification                               │              │
│      │  - Session ID                                          │              │
│      │  - URLs to test                                        │              │
│      │  - Verification folder path                            │              │
│      │                                                        │              │
│      │  Subagent does NOT receive:                            │              │
│      │  - Implementation code                                 │              │
│      │  - Commit messages                                     │              │
│      │  - Coder's notes/reasoning                             │              │
│      │                                                        ▼              │
│      │                                          ┌───────────────────────┐    │
│      │                                          │ VERIFICATION SUBAGENT │    │
│      │                                          │                       │    │
│      │                                          │ - Run tests           │    │
│      │                                          │ - Navigate UI         │    │
│      │                                          │ - Take screenshots    │    │
│      │                                          │ - Compare to spec     │    │
│      │                                          │ - Write verification/ │    │
│      │                                          └───────────┬───────────┘    │
│      │                                                      │                │
│      │                              ┌───────────────────────┴────────────┐   │
│      │                              │                                    │   │
│      │                         VERIFIED                            NOT_VERIFIED│
│      │                              │                                    │   │
│      │                              ▼                                    ▼   │
│      │                     READY_FOR_REVIEW                    Coder fixes   │
│      │                                                         Re-run subagent│
│      │                                                         (max 3 attempts)│
│      └──────────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REVIEW SESSION                                    │
│                                                                              │
│   PHASE 1: ADVERSARIAL EVIDENCE REVIEW (before looking at code)              │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Reviewer mindset: "Feature is BROKEN. I must prove it."             │   │
│   │                                                                     │   │
│   │ 1. Load verification/{session_id}/verification.md                  │   │
│   │ 2. For each screenshot:                                            │   │
│   │    - What SHOULD this show?                                        │   │
│   │    - What DOES it show?                                            │   │
│   │    - What's MISSING?                                               │   │
│   │    - What's WRONG?                                                 │   │
│   │                                                                     │   │
│   │ 3. Execute attack vectors:                                         │   │
│   │    - Edge cases (empty, null, special chars)                       │   │
│   │    - Boundary values (min, max, overflow)                          │   │
│   │    - Error paths (force failures)                                  │   │
│   │    - State corruption (rapid actions, navigation)                  │   │
│   │                                                                     │   │
│   │ 4. Document each attack: attempted / result / evidence             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   PHASE 2: VERDICT                                                           │
│                                                                              │
│   ┌────────────────────────────────────────────────┐                        │
│   │ Did ANY attack prove feature broken?            │                        │
│   │                                                │                        │
│   │   YES ──► REQUEST_CHANGES                      │                        │
│   │           (document which attack succeeded)    │                        │
│   │                                                │                        │
│   │   NO  ──► Proceed to code review               │                        │
│   │           (feature behaviorally verified)      │                        │
│   └────────────────────────────────────────────────┘                        │
│                                                                              │
│   PHASE 3: CODE REVIEW (only if verification passed)                         │
│   - Standard code review against checklist                                   │
│   - May still REQUEST_CHANGES for code quality issues                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Verification Folder Structure

```
{AGENT_STATE_DIR}/
├── progress/
│   └── {session_id}.md              # Session summary (existing, high-level)
├── verification/
│   └── {session_id}/
│       ├── verification.md          # Detailed verification report
│       ├── screenshots/
│       │   ├── 001-initial-state.png
│       │   ├── 002-action-taken.png
│       │   ├── 003-result-state.png
│       │   └── ...
│       └── test_evidence/
│           └── test_output.txt      # Raw test runner output
├── progress.json
├── reviews.json
└── feature_list.json
```

### Relationship to Existing Structure

| File/Folder | Purpose | Who Creates | Who Reads |
|-------------|---------|-------------|-----------|
| `progress/{session_id}.md` | High-level session summary | All agents | All agents |
| `verification/{session_id}/` | Detailed proof of correctness | IMPLEMENT, FIX (via subagent) | REVIEW |
| `verification/{session_id}/verification.md` | Verification report | Verification subagent | REVIEW |
| `verification/{session_id}/screenshots/` | Visual evidence | Verification subagent | REVIEW |

---

## Verification Report Format

### For IMPLEMENT Agent (Feature Implementation)

```markdown
# Verification Report: Session {session_id}

## Metadata
- **Session ID:** {session_id}
- **Agent Type:** IMPLEMENT
- **Timestamp:** {ISO timestamp}
- **Verified By:** Verification Subagent (fresh context)

## Features Verified
| Feature ID | Name | Specification Summary |
|------------|------|----------------------|
| F001 | User Login | Users can log in with email/password |

---

## Test Evidence

### Tests Created
| Test Name | Purpose | What It Verifies |
|-----------|---------|------------------|
| `test_login_valid_credentials` | Happy path | User logs in with correct credentials |
| `test_login_invalid_password` | Negative case | Error displayed for wrong password |
| `test_login_empty_fields` | Edge case | Validation prevents empty submission |
| `test_login_sql_injection` | Security | Input is properly escaped |

### Test Execution
- **Command:** `pytest tests/test_auth.py -v`
- **Exit Code:** 0
- **Result:** 4 passed, 0 failed
- **Raw Output:** See `test_evidence/test_output.txt`

---

## Visual Evidence

### Screenshot: 001-initial-state.png
- **URL:** http://localhost:3000/login
- **What This Shows:** Login page with email and password input fields, "Sign In" button
- **Expected Per Spec:** Login form with email/password fields
- **Match:** YES

### Screenshot: 002-form-filled.png
- **URL:** http://localhost:3000/login
- **Action Taken:** Entered "testuser@example.com" and "ValidPass123"
- **What This Shows:** Form populated with credentials
- **Verification Step:** Confirms input fields accept text

### Screenshot: 003-login-success.png
- **URL:** http://localhost:3000/dashboard
- **What This Shows:** Dashboard page with "Welcome, testuser" in header
- **Expected Per Spec:** Redirect to dashboard after login, display username
- **Match:** YES

### Screenshot: 004-error-state.png
- **URL:** http://localhost:3000/login
- **Action Taken:** Entered wrong password
- **What This Shows:** Error message "Invalid credentials" displayed
- **Expected Per Spec:** Clear error message on failed login
- **Match:** YES

---

## Specification Compliance Checklist

| Requirement | Evidence | Status |
|-------------|----------|--------|
| User can enter email | Screenshot 002 | VERIFIED |
| User can enter password | Screenshot 002 | VERIFIED |
| Valid credentials → dashboard | Screenshot 003 | VERIFIED |
| Invalid credentials → error | Screenshot 004 | VERIFIED |
| Password field masked | Screenshot 002 | VERIFIED |

---

## Verification Conclusion

**Status:** VERIFIED
**Reason:** All specification requirements have corresponding evidence. All tests pass. UI behavior matches expected behavior in all tested scenarios.

---

## Limitations Noted

- Did not test: password reset flow (separate feature)
- Did not test: session timeout (not in spec)
- Did not test: concurrent logins (not in spec)
```

### For FIX Agent (Issue Resolution)

```markdown
# Verification Report: Session {session_id}

## Metadata
- **Session ID:** {session_id}
- **Agent Type:** FIX
- **Review Addressed:** R{review_id}
- **Timestamp:** {ISO timestamp}

## Issues Verified as Fixed

### Issue: R1-C1 (CRITICAL)
- **Original Problem:** Login button not clickable on mobile viewport
- **Evidence of Fix:**
  - Screenshot `001-mobile-before-fix.png`: N/A (issue existed before)
  - Screenshot `002-mobile-after-fix.png`: Login button visible and clickable at 375px width
- **Verification Method:** Tested at mobile viewport (375px)
- **Status:** FIXED

### Issue: R1-M1 (MAJOR)
- **Original Problem:** No loading indicator during authentication
- **Evidence of Fix:**
  - Screenshot `003-loading-state.png`: Spinner visible during API call
- **Verification Method:** Observed loading state during slow network simulation
- **Status:** FIXED

---

## Regression Check

### Previously Working Features
| Feature | Status | Evidence |
|---------|--------|----------|
| Desktop login | Still works | Screenshot 004 |
| Error messages | Still works | Screenshot 005 |

---

## Verification Conclusion

**Status:** VERIFIED
**Issues Fixed:** 2 of 2
**Regressions:** None detected
```

---

## Subagent Verification Protocol

### Subagent Spawning

The IMPLEMENT/FIX agent spawns a verification subagent using the Task tool:

```
IMPLEMENT agent completes coding
    │
    ▼
python3 scripts/verification.py spawn \
  --session-id {session_id} \
  --feature-ids "F001,F002" \
  --verification-dir "{AGENT_STATE_DIR}/verification/{session_id}"
    │
    ▼
Task tool launches subagent with:
  - subagent_type: "verification"
  - prompt: Generated from verification_subagent_prompt.md
  - Isolated context (no implementation details)
```

### Subagent Input (What It Receives)

```json
{
  "session_id": 15,
  "feature_specifications": [
    {
      "id": "F001",
      "name": "User Login",
      "description": "...",
      "verification_steps": ["..."]
    }
  ],
  "test_commands": ["pytest tests/", "npm run test"],
  "app_urls": {
    "frontend": "http://localhost:3000",
    "backend": "http://localhost:8000"
  },
  "verification_output_dir": ".agent_state/verification/15"
}
```

### Subagent Output

```json
{
  "status": "VERIFIED" | "NOT_VERIFIED" | "INCOMPLETE",
  "verification_report_path": ".agent_state/verification/15/verification.md",
  "screenshots_captured": 4,
  "tests_passed": true,
  "issues_found": [],
  "reason": "All specification requirements verified"
}
```

### Subagent Failure Handling

| Outcome | Meaning | Coder Response |
|---------|---------|----------------|
| `VERIFIED` | All checks passed | Proceed to READY_FOR_REVIEW |
| `NOT_VERIFIED` | Checks failed | Fix issues, re-spawn subagent |
| `INCOMPLETE` | Subagent couldn't finish | Coder completes verification manually (last resort) |

**Retry limits:**
- Max subagent attempts: 3
- After 3 NOT_VERIFIED: Coder must fix or escalate
- After INCOMPLETE: Coder takes over verification

---

## Adversarial Review Protocol

### Mindset Shift

| Current Approach | Adversarial Approach |
|-----------------|---------------------|
| "Does verification look complete?" | "Can I find a hole in the verification?" |
| "Tests pass, looks good" | "What cases didn't they test?" |
| "Screenshot shows feature" | "What's NOT in this screenshot that should be?" |
| Start: assume correct | Start: assume broken |
| Goal: confirm working | Goal: prove broken |
| "Backend works, frontend is separate" | "If UI is wrong, feature is broken. REJECT." |
| "Observed issue is minor/edge case" | "Any issue = REJECT. No exceptions." |

### Mandatory Attack Checklist

The reviewer MUST attempt ALL attacks before concluding feature is not broken:

```markdown
## Adversarial Attack Log

### Attack 1: Empty Input
- **Target:** All input fields
- **Method:** Submit form with empty fields
- **Expected Failure:** Validation bypass or crash
- **Observed Result:** [document what happened]
- **Screenshot:** attack-001-empty-input.png
- **Conclusion:** BROKEN / NOT_BROKEN

### Attack 2: Invalid Input Types
- **Target:** All input fields
- **Method:** Enter numbers in text fields, text in number fields
- **Expected Failure:** Type coercion errors
- **Observed Result:** [document what happened]
- **Screenshot:** attack-002-invalid-types.png
- **Conclusion:** BROKEN / NOT_BROKEN

### Attack 3: Boundary Values
- **Target:** Numeric inputs, text lengths
- **Method:** Test min-1, min, max, max+1 values
- **Expected Failure:** Overflow, truncation, or crash
- **Observed Result:** [document what happened]
- **Screenshot:** attack-003-boundaries.png
- **Conclusion:** BROKEN / NOT_BROKEN

### Attack 4: Special Characters
- **Target:** Text inputs
- **Method:** Enter <script>, SQL injection, unicode, emoji
- **Expected Failure:** XSS, SQLi, encoding errors
- **Observed Result:** [document what happened]
- **Screenshot:** attack-004-special-chars.png
- **Conclusion:** BROKEN / NOT_BROKEN

### Attack 5: Rapid Actions
- **Target:** Buttons, form submissions
- **Method:** Double-click, rapid repeated clicks
- **Expected Failure:** Duplicate submissions, race conditions
- **Observed Result:** [document what happened]
- **Screenshot:** attack-005-rapid-actions.png
- **Conclusion:** BROKEN / NOT_BROKEN

### Attack 6: Navigation Abuse
- **Target:** Application flow
- **Method:** Back button, refresh, direct URL access
- **Expected Failure:** State corruption, unauthorized access
- **Observed Result:** [document what happened]
- **Screenshot:** attack-006-navigation.png
- **Conclusion:** BROKEN / NOT_BROKEN

---

## Attack Summary

| Attack | Result |
|--------|--------|
| Empty Input | NOT_BROKEN |
| Invalid Types | NOT_BROKEN |
| Boundary Values | **BROKEN** - max+1 caused crash |
| Special Characters | NOT_BROKEN |
| Rapid Actions | NOT_BROKEN |
| Navigation Abuse | NOT_BROKEN |

## Verdict Determination

- **Any BROKEN?** YES
- **Verdict:** REQUEST_CHANGES
- **Blocking Issue:** Boundary value handling for field X
```

### Verdict Rules

| Condition | Verdict |
|-----------|---------|
| ANY attack resulted in BROKEN | REQUEST_CHANGES |
| Verification evidence incomplete | REQUEST_CHANGES |
| Cannot reproduce claimed behavior | REQUEST_CHANGES |
| **ANY observed behavioral issue** | **REQUEST_CHANGES** |
| ALL attacks NOT_BROKEN + evidence complete | Proceed to code review |
| Code review finds critical/major issues | REQUEST_CHANGES |
| Code review clean OR only minor issues | APPROVE / PASS_WITH_COMMENTS |

---

### CRITICAL: Zero-Tolerance for Observed Issues

**ANY suspicion of incomplete functionality = AUTOMATIC REJECTION.**

This is non-negotiable. The following rationalizations are INVALID and must NEVER lead to approval:

| Invalid Rationalization | Why It's Wrong |
|------------------------|----------------|
| "Backend works, frontend is separate" | User sees frontend. If it's broken, feature is broken. |
| "Tests pass" | Tests can be incomplete. Visual evidence overrides test results. |
| "Code change is correct" | Correct code that doesn't produce correct behavior = broken. |
| "This is a different bug" | If observed during verification, it blocks approval. File new bug, reject current. |
| "Spec only mentions X layer" | End-to-end behavior matters. Partial fixes are incomplete. |
| "Works in API, broken in UI" | If users interact via UI, UI must work. |
| "Edge case / minor issue" | Document it, reject it. No exceptions. |

**The Rule:** If you observe ANYTHING that suggests the feature/fix does not work correctly from the end-user's perspective, you MUST reject. Period.

**Evidence over inference:** What you SEE in the browser/API response trumps what the code/tests suggest SHOULD happen. If there's a discrepancy, the visual evidence is correct and the implementation is wrong.

**Example of WRONG reviewer behavior:**
```
Reviewer observes: "Frontend displays oldest sessions at top instead of newest"
Reviewer rationalizes: "But BUG-005 is about backend parser, and that's fixed"
Reviewer concludes: "APPROVE"

THIS IS WRONG. The correct response is REQUEST_CHANGES.
```

**Example of CORRECT reviewer behavior:**
```
Reviewer observes: "Frontend displays oldest sessions at top instead of newest"
Reviewer notes: "Bug spec says 'most recent sessions should appear at top'"
Reviewer concludes: "Feature does not work as specified. REQUEST_CHANGES."
```

---

## Agent Responsibilities Matrix

| Agent | Creates Verification? | Verification Focus | Reviews Verification? |
|-------|----------------------|--------------------|-----------------------|
| IMPLEMENT | Yes (via subagent) | Feature matches specification | No |
| FIX | Yes (via subagent) | Issue resolved, no regressions | No |
| REVIEW | No | N/A | Yes (adversarial) |
| GLOBAL_FIX | Yes | Tech debt resolved | No |
| ARCHITECTURE | No | N/A | No (creates issues only) |

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `prompts/verification_subagent_prompt.md` | Prompt for verification subagent |
| `scripts/verification.py` | CLI for spawning/managing verification |
| `prompts/adversarial_attack_checklist.md` | Required attacks for reviewer |

### Modified Files

| File | Changes |
|------|---------|
| `prompts/coding_prompt.md` | Add Step: Spawn verification subagent |
| `prompts/fix_prompt.md` | Add Step: Spawn verification subagent |
| `prompts/reviewer_prompt.md` | Replace verification with adversarial protocol |
| `prompts/global_fix_prompt.md` | Add verification subagent step |
| `ARCHITECTURE.md` | Document verification system |

---

## Detailed Changes by File

### 1. `prompts/verification_subagent_prompt.md` (NEW)

```markdown
# YOUR ROLE - VERIFICATION SUBAGENT

You are an independent verifier with a FRESH context. You have NO knowledge of
how the feature was implemented. Your job is to verify the feature works
according to its specification.

## CRITICAL CONSTRAINTS

You DO NOT have access to:
- Implementation code
- Commit history
- The coder's reasoning or notes
- Any context from the implementation session

You ONLY have:
- Feature specification
- Running application URLs
- Test commands

## YOUR MISSION

Verify that the implemented feature matches its specification through:
1. Running automated tests
2. Manual UI verification with screenshots
3. Documenting evidence

## STEP 1: RUN AUTOMATED TESTS
[Test execution instructions]

## STEP 2: VISUAL VERIFICATION
[Playwright MCP instructions]

## STEP 3: WRITE VERIFICATION REPORT
[Report format and structure]

## STEP 4: RETURN VERDICT
Return structured result:
- VERIFIED: All checks passed
- NOT_VERIFIED: Specific failures found
- INCOMPLETE: Could not complete verification
```

### 2. `prompts/coding_prompt.md` (MODIFY)

Add after current Step 8 (Verification Before Completion):

```markdown
## STEP 9: SPAWN VERIFICATION SUBAGENT (MANDATORY)

You MUST NOT verify your own work. A fresh-context subagent will verify.

### 9.1 Prepare Verification Request

```bash
# Create verification input
SESSION_ID=$(python3 scripts/progress.py next-session-id)
FEATURE_IDS="<comma-separated feature IDs you implemented>"

python3 scripts/verification.py prepare \
  --session-id $SESSION_ID \
  --feature-ids "$FEATURE_IDS" \
  --verification-dir "{{AGENT_STATE_DIR}}/verification/$SESSION_ID"
```

### 9.2 Launch Verification Subagent

Use the Task tool to spawn the verification subagent:

```
Task tool:
  subagent_type: "verification"
  prompt: "Verify features $FEATURE_IDS for session $SESSION_ID"
```

### 9.3 Handle Verification Result

| Result | Action |
|--------|--------|
| VERIFIED | Proceed to Step 10 (Commit) |
| NOT_VERIFIED | Fix identified issues, re-run Step 9 |
| INCOMPLETE | Complete verification manually (document why) |

**Max attempts:** 3 subagent runs. After 3 NOT_VERIFIED results, you must
either fix the issues or escalate with detailed documentation.

⛔ **DO NOT proceed to READY_FOR_REVIEW without VERIFIED status**
```

### 3. `prompts/reviewer_prompt.md` (MAJOR REWRITE)

Replace Steps 4-6 with adversarial protocol:

```markdown
## STEP 4: ADVERSARIAL VERIFICATION REVIEW (BEFORE CODE)

**Mindset: The feature is BROKEN. Your job is to prove it.**

### 4.1 Load Verification Evidence

```bash
SESSION_ID=$(python3 scripts/progress.py get-session -1 --field session_id)
cat "{{AGENT_STATE_DIR}}/verification/$SESSION_ID/verification.md"
ls "{{AGENT_STATE_DIR}}/verification/$SESSION_ID/screenshots/"
```

### 4.2 Analyze Screenshots Critically

For EACH screenshot in the verification folder:

| Question | Your Answer |
|----------|-------------|
| What SHOULD this show per spec? | [answer] |
| What DOES this actually show? | [answer] |
| What's MISSING that should be visible? | [answer] |
| What's WRONG that shouldn't be there? | [answer] |

### 4.3 Execute Attack Vectors (MANDATORY)

You MUST attempt ALL attacks in `adversarial_attack_checklist.md`.

Document each attack:
- What you tried
- What you expected to break
- What actually happened
- Screenshot evidence
- Conclusion: BROKEN or NOT_BROKEN

### 4.4 Determine Behavioral Verdict

| Condition | Action |
|-----------|--------|
| ANY attack = BROKEN | REQUEST_CHANGES (skip code review) |
| ALL attacks = NOT_BROKEN | Proceed to Step 5 (Code Review) |

---

## STEP 5: CODE REVIEW (only if verification passed)

Review code against `review_checklist.md`.

Note: You already know the feature WORKS (from Step 4).
Now verify the code QUALITY.
```

### 4. `scripts/verification.py` (NEW)

```python
#!/usr/bin/env python3
"""
Verification management CLI.

Commands:
  prepare    - Prepare verification input for subagent
  status     - Check verification status for a session
  list       - List all verification reports
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime

def prepare(args):
    """Prepare verification input file for subagent."""
    verification_dir = Path(args.verification_dir)
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "screenshots").mkdir(exist_ok=True)
    (verification_dir / "test_evidence").mkdir(exist_ok=True)

    # Load feature specifications
    features = []
    feature_ids = [f.strip() for f in args.feature_ids.split(",")]

    with open("feature_list.json") as f:
        feature_list = json.load(f)
        for fid in feature_ids:
            for feature in feature_list.get("features", []):
                if feature["id"] == fid:
                    features.append(feature)

    # Create verification input
    verification_input = {
        "session_id": args.session_id,
        "feature_specifications": features,
        "test_commands": ["pytest tests/", "npm run test"],
        "app_urls": {
            "frontend": "http://localhost:3000",
            "backend": "http://localhost:8000"
        },
        "verification_output_dir": str(verification_dir),
        "created_at": datetime.now().isoformat()
    }

    input_file = verification_dir / "verification_input.json"
    with open(input_file, "w") as f:
        json.dump(verification_input, f, indent=2)

    print(f"Verification input prepared: {input_file}")
    return str(input_file)

def status(args):
    """Check verification status for a session."""
    verification_dir = Path(f".agent_state/verification/{args.session_id}")

    if not verification_dir.exists():
        print(json.dumps({"status": "NOT_STARTED"}))
        return

    report_file = verification_dir / "verification.md"
    if not report_file.exists():
        print(json.dumps({"status": "IN_PROGRESS"}))
        return

    # Parse verification.md for status
    content = report_file.read_text()
    if "**Status:** VERIFIED" in content:
        status = "VERIFIED"
    elif "**Status:** NOT_VERIFIED" in content:
        status = "NOT_VERIFIED"
    else:
        status = "INCOMPLETE"

    screenshots = list((verification_dir / "screenshots").glob("*.png"))

    print(json.dumps({
        "status": status,
        "report_path": str(report_file),
        "screenshots_count": len(screenshots)
    }))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    # prepare command
    prep = subparsers.add_parser("prepare")
    prep.add_argument("--session-id", required=True, type=int)
    prep.add_argument("--feature-ids", required=True)
    prep.add_argument("--verification-dir", required=True)

    # status command
    stat = subparsers.add_parser("status")
    stat.add_argument("--session-id", required=True, type=int)

    args = parser.parse_args()

    if args.command == "prepare":
        prepare(args)
    elif args.command == "status":
        status(args)
```

---

## Implementation Phases

### Phase 1: Verification Folder Structure
1. Create `scripts/verification.py` with `prepare` and `status` commands
2. Update agent prompts to create verification folders
3. Define verification.md template

**Files changed:**
- NEW: `scripts/verification.py`
- MODIFY: `prompts/coding_prompt.md` (add folder creation)
- MODIFY: `prompts/fix_prompt.md` (add folder creation)

### Phase 2: Verification Subagent
1. Create `prompts/verification_subagent_prompt.md`
2. Add subagent spawning logic to IMPLEMENT prompt
3. Add subagent spawning logic to FIX prompt
4. Handle subagent results (VERIFIED/NOT_VERIFIED/INCOMPLETE)

**Files changed:**
- NEW: `prompts/verification_subagent_prompt.md`
- MODIFY: `prompts/coding_prompt.md` (add subagent spawn step)
- MODIFY: `prompts/fix_prompt.md` (add subagent spawn step)

### Phase 3: Adversarial Review
1. Create `prompts/adversarial_attack_checklist.md`
2. Rewrite `prompts/reviewer_prompt.md` with adversarial protocol
3. Add verification-first review order

**Files changed:**
- NEW: `prompts/adversarial_attack_checklist.md`
- MODIFY: `prompts/reviewer_prompt.md` (major rewrite)

### Phase 4: Global Fix Integration
1. Add verification to `prompts/global_fix_prompt.md`

**Files changed:**
- MODIFY: `prompts/global_fix_prompt.md`

### Phase 5: Documentation
1. Update `ARCHITECTURE.md` with verification system
2. Add verification section to README

**Files changed:**
- MODIFY: `ARCHITECTURE.md`

---

## Screenshot Storage Considerations

### Option A: Store in Git (Simple)
- Screenshots stored directly in `verification/{session_id}/screenshots/`
- Pros: Simple, self-contained
- Cons: Repo bloat over time

### Option B: Git LFS (Recommended for large projects)
```bash
git lfs install
git lfs track "*.png"
git lfs track "*.jpg"
```

### Option C: External Storage
- Store screenshots in S3/GCS
- Keep only references in verification.md
- Pros: No repo bloat
- Cons: More complex setup

**Recommendation:** Start with Option A (simple). Migrate to Option B if repo size becomes problematic.

---

## Metrics & Monitoring

### Verification Success Rate
Track over time:
- % of sessions with VERIFIED on first attempt
- Average subagent attempts before VERIFIED
- % of INCOMPLETE (manual fallback)

### Adversarial Review Effectiveness
Track:
- % of reviews that found issues via attacks (vs code review)
- Which attack types most frequently find bugs
- Time spent on adversarial phase vs code review phase

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Subagent takes too long | Set max_turns limit, timeout |
| Subagent cannot complete | INCOMPLETE status triggers coder fallback |
| Screenshot storage bloat | Git LFS or external storage |
| Adversarial review becomes perfunctory | Mandatory checklist with evidence |
| Subagent has access to implementation | Strict input isolation, no code access |
| **Reviewer rationalizes partial success** | **Zero-tolerance rule: any observed issue = reject. "Backend works" is not valid approval reason if UI is broken.** |
| **Tests pass but behavior is wrong** | **Visual/behavioral evidence overrides test results. If you see it broken, it's broken.** |

---

## Success Criteria

1. **Bias Elimination:** Verification is performed by independent agent with no implementation knowledge
2. **Evidence Trail:** Every approved feature has verification folder with screenshots and test results
3. **Adversarial Rigor:** Every review includes documented attack attempts
4. **No Self-Approval:** Coder cannot claim READY_FOR_REVIEW without subagent VERIFIED status
5. **Zero-Tolerance Enforcement:** ANY observed behavioral issue results in rejection—no rationalizations about "backend works" or "tests pass" when end-user behavior is broken
