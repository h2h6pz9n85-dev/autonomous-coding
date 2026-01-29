# Code Review Checklist

Evaluate implementations against these criteria. Record PASS/FAIL for each category.

## Priority Guide

| Priority | Categories | Impact |
|----------|------------|--------|
| **P0 - Blockers** | Functionality, Security, Testing | Automatic REQUEST_CHANGES if FAIL |
| **P1 - Important** | Code Quality, Error Handling | REQUEST_CHANGES if multiple FAILs |
| **P2 - Polish** | Maintainability | PASS_WITH_COMMENTS if minor issues |

---

## 1. FUNCTIONALITY & COMPLETENESS [P0]

- [ ] Feature is fully implemented as specified (not stubbed, mocked, or TODO'd)
- [ ] All acceptance criteria from the spec are met
- [ ] Feature works end-to-end through the actual UI
- [ ] No `// TODO` comments, empty catch blocks, or placeholder return values
- [ ] No console.log/print debugging statements left in
- [ ] Functions actually perform their stated purpose (not returning mock data)

---

## 2. SECURITY [P0]

- [ ] All endpoints properly authenticated (where required)
- [ ] SQL injection prevented (parameterized queries)
- [ ] XSS prevented (output encoding)
- [ ] No hardcoded API keys, passwords, or secrets in code
- [ ] Input validation on all user-supplied data

---

## 3. TESTING [P0]

- [ ] All new code has corresponding tests
- [ ] Happy path tested with expected inputs/outputs
- [ ] Invalid/empty inputs handled and tested
- [ ] Edge cases tested (boundary values, empty collections)
- [ ] Tests are deterministic (no flaky tests)

---

## 4. CODE QUALITY [P1]

- [ ] No God classes (>300 lines) or long methods (>50 lines)
- [ ] No duplicate code blocks
- [ ] Clear separation between data access, business logic, and presentation
- [ ] Names reveal intent (avoid `data`, `info`, `temp`, `x`)
- [ ] Functions do one thing and are small (<20 lines ideal)

---

## 5. ERROR HANDLING [P1]

- [ ] Exceptions caught at appropriate levels (not bare except)
- [ ] Errors logged with context
- [ ] User-facing errors are friendly (no stack traces exposed)
- [ ] API returns appropriate status codes (400, 401, 403, 404, 500)

---

## 6. MAINTAINABILITY [P2]

- [ ] Code is easy to understand without extensive comments
- [ ] Dependencies are injectable (not hardcoded)
- [ ] No dead code or unused imports
- [ ] Consistent style throughout
