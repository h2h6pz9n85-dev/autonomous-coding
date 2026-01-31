# Adversarial Attack Checklist

**MANDATORY for REVIEW agent.** You MUST attempt ALL attacks before concluding a feature is not broken.

---

## Mindset

**Assume the feature is BROKEN. Your job is to prove it.**

| Wrong Approach | Correct Approach |
|----------------|------------------|
| "Does it look like it works?" | "How can I break this?" |
| "Tests pass, good enough" | "What cases did they NOT test?" |
| "Screenshot shows the feature" | "What's MISSING from this screenshot?" |
| "Backend works correctly" | "Does the USER see correct behavior?" |

---

## ZERO-TOLERANCE RULE

**ANY observed behavioral issue = AUTOMATIC REJECTION**

This is non-negotiable. These rationalizations are INVALID:

| Invalid Thought | Reality |
|-----------------|---------|
| "Backend works, frontend is separate" | If UI is wrong, feature is broken. REJECT. |
| "Tests pass" | Tests can be incomplete. Visual evidence overrides. |
| "Code change is correct" | Correct code + wrong behavior = broken. REJECT. |
| "This is a different bug" | If seen during verification, it blocks approval. REJECT. |
| "Spec only mentions backend" | End-to-end behavior matters. REJECT if UI fails. |
| "It's just an edge case" | Edge cases are bugs. REJECT. |

---

## Attack Categories

### Attack 1: Empty Input

**Target:** All input fields, form submissions
**Method:** Submit with empty/blank values
**Expected Failures:** Validation bypass, null pointer errors, database constraint violations

```markdown
### Attack 1: Empty Input
- **Target:** [List all input fields]
- **Method:** Submit form with all fields empty
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-001-empty-input.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 2: Invalid Input Types

**Target:** All input fields
**Method:** Enter wrong data types (numbers in text, text in numbers, dates in wrong format)
**Expected Failures:** Type coercion errors, display issues, crashes

```markdown
### Attack 2: Invalid Input Types
- **Target:** [List fields and types tested]
- **Method:** Entered [specific invalid inputs]
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-002-invalid-types.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 3: Boundary Values

**Target:** Numeric inputs, text length limits, date ranges
**Method:** Test min-1, min, max, max+1 values
**Expected Failures:** Overflow, underflow, truncation, display issues

```markdown
### Attack 3: Boundary Values
- **Target:** [Numeric/limited fields]
- **Method:** Tested values: [list specific values]
  - min-1: [value]
  - min: [value]
  - max: [value]
  - max+1: [value]
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-003-boundaries.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 4: Special Characters

**Target:** Text inputs
**Method:** Enter `<script>alert(1)</script>`, `'; DROP TABLE users;--`, unicode, emoji, newlines
**Expected Failures:** XSS, SQL injection, encoding errors, display corruption

```markdown
### Attack 4: Special Characters
- **Target:** [Text input fields]
- **Method:** Entered special characters:
  - XSS attempt: `<script>alert(1)</script>`
  - SQL injection: `'; DROP TABLE users;--`
  - Unicode: `测试 🎉 ñ`
  - Newlines/tabs
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-004-special-chars.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 5: Rapid Actions

**Target:** Buttons, form submissions, toggles
**Method:** Double-click, rapid repeated clicks, quick toggle on/off
**Expected Failures:** Duplicate submissions, race conditions, state corruption

```markdown
### Attack 5: Rapid Actions
- **Target:** [Buttons/interactive elements]
- **Method:**
  - Double-clicked submit button
  - Rapid clicks (5+ in 1 second)
  - Quick toggle on/off/on
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-005-rapid-actions.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 6: Navigation Abuse

**Target:** Application flow, state management
**Method:** Back button after submit, refresh during operation, direct URL access, multiple tabs
**Expected Failures:** State corruption, unauthorized access, duplicate operations, stale data

```markdown
### Attack 6: Navigation Abuse
- **Target:** Application flow
- **Method:**
  - Hit back button after successful submit
  - Refreshed page during loading
  - Accessed URL directly without login
  - Opened same form in two tabs, submitted both
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-006-navigation.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

### Attack 7: Network Interruption (if applicable)

**Target:** API calls, form submissions
**Method:** Slow network simulation, timeout scenarios
**Expected Failures:** Hanging UI, no error message, lost data

```markdown
### Attack 7: Network Interruption
- **Target:** [API-dependent features]
- **Method:** Throttled network / simulated timeout
- **Expected Failure:** [What might break]
- **Observed Result:** [What actually happened]
- **Screenshot:** attack-007-network.png
- **Conclusion:** BROKEN / NOT_BROKEN
```

---

## Attack Summary Template

After completing all attacks, summarize:

```markdown
## Attack Summary

| Attack | Target | Result |
|--------|--------|--------|
| Empty Input | All forms | NOT_BROKEN |
| Invalid Types | Email, phone fields | NOT_BROKEN |
| Boundary Values | Age field | **BROKEN** - allows age > 200 |
| Special Characters | Name field | NOT_BROKEN |
| Rapid Actions | Submit button | NOT_BROKEN |
| Navigation Abuse | Checkout flow | **BROKEN** - double submission |

## Verdict Determination

- **Any BROKEN?** YES
- **Blocking Issues:**
  1. Age field accepts invalid values (> 200)
  2. Double submission possible on checkout
- **Verdict:** REQUEST_CHANGES
```

---

## Verdict Rules

| Condition | Verdict | Action |
|-----------|---------|--------|
| ANY attack = BROKEN | REQUEST_CHANGES | Document which attacks succeeded |
| ANY behavioral issue observed | REQUEST_CHANGES | Even if not from attacks |
| Verification evidence incomplete | REQUEST_CHANGES | Cannot verify = cannot approve |
| Cannot reproduce claimed behavior | REQUEST_CHANGES | Evidence doesn't match claims |
| ALL attacks NOT_BROKEN + evidence complete | Proceed to code review | Feature verified behaviorally |

---

## REMEMBER

> "If you observed ANYTHING wrong during verification—regardless of test results, code quality, or which layer supposedly 'works'—the correct action is REQUEST_CHANGES. Period."

The feature either works for the END USER or it doesn't. Backend correctness means nothing if the frontend is broken.
