# Brownfield Mode: Autonomous Coding for Existing Projects

> **Objective**: Enable the autonomous coding framework to safely and effectively operate within massive, pre-existing codebases ("Brownfield" projects) without duplication or regression.

## Core Philosophy

**"Invest upfront, execute with awareness."**

Unlike greenfield projects where the agent defines the structure, brownfield projects require a deep, accurate map of the territory before changes can be made. We reject "scope-limited audits" in favor of a **Multi-Phase Autonomous Audit** that builds a "Unified Knowledge Base" of the application.

---

## Architecture: The Multi-Phase Audit Pipeline

This workflow transforms an opaque codebase into structured knowledge (`feature_list.json` + `issues.json`) without requiring human manual entry.

### Phase 0: Static Analysis (Pre-Audit)
*Goal: Cheaply identify structural hotspots, quality issues, and security risks.*

**Tooling**: SonarQube, Semgrep, ESLint, or native AST parsers.
**Process**: Programmatic scan (no LLM).
**Output**: `static_analysis_report.json`
- Code smells (complexity, duplication)
- Security vulnerabilities
- Dependency graph (imports/exports)
- Metrics (LOC per module)

### Phase 1: Entry Point Discovery (The "Fan-Out" Pattern)
*Goal: Understand what the application **does** by observing how it interacts with the world.*

#### 1a. Discovery (Orchestrator Agent)
Scans for "Triggers" that initiate code execution:
- **API Endpoints**: REST, GraphQL, gRPC routes.
- **Async Consumers**: Kafka listeners, RabbitMQ consumers, SQS handlers.
- **Scheduled Tasks**: Cron jobs, Celery tasks, Quartz schedulers.

#### 1b. Deep Analysis (Parallel Agents)
**"Fan-Out"**: The Orchestrator groups entry points by domain (e.g., `Auth`, `Billing`, `Reports`) and spawns dedicated Analysis Agents.

Each Analysis Agent:
1.  **Traces Execution**: Follows the code path from entry point deeper into services/repositories.
2.  **Builds Call Graphs**: Maps implicit dependencies.
3.  **Consults Static Analysis**: Checks `static_analysis_report.json` for the code paths it traverses. if it finds a complex method in a critical path, it flags it.
4.  **Documents Behavior**: Writes a summary of what the feature actually does.

#### 1c. Reconciliation (The "Merge" Agent)
Consolidates parallel reports to identify shared dependencies.
- **Identifies Shared Services**: e.g., "Both `Billing` and `Users` depend on `AuthService`."
- **Labels Infrastructure**: Marks components like `EmailService` or `LogHandler` as cross-cutting concerns.
- **Resolves Overlaps**: Dedupes discovered logic.

### Phase 2: Test & Verification Analysis
*Goal: Understand safety nets and covered scenarios.*

**Process**:
- Parse test names/descriptions (often richer than code comments).
- Map tests to the Entry Points discovered in Phase 1.
- Identify "Critical Paths with Zero Coverage".

### Phase 3: Documentation Reality Check
*Goal: Align human intent (Docs) with machine reality (Code).*

**Process**:
- Parse `README.md`, `/docs`, API specs (OpenAPI/Swagger).
- Compare against Phase 1 Findings.
- **Discrepancy Detection**: Flag instances where "Docs say X, but Code does Y".

---

## The Unified Knowledge Base (Outputs)

The Audit results in two artifacts that drive the implementation workflows.

### 1. `feature_list.json` (The Map)
An inventory of **existing** capabilities.
```json
{
  "features": [
    {
      "id": "EXIST-001",
      "name": "User Registration (API)",
      "source": "existing",
      "status": "stable",
      "entry_points": ["POST /api/register"],
      "dependencies": ["AuthService", "UserRepository", "EmailService"],
      "test_coverage": "high",
      "documentation": "consistent",
      "summary": "Validates input, hashes password, saves user, sends welcome email."
    },
    ...
  ]
}
```

### 2. `issues.json` (The Debt Ledger)
Actionable items discovered during audit.
```json
{
  "issues": [
    {
      "id": "ISSUE-001",
      "type": "security",
      "severity": "critical",
      "location": "src/auth/legacy_login.py",
      "description": "SQL Injection vulnerability in legacy login path.",
      "context": "Discovered during analysis of GET /login/v1"
    },
    {
      "id": "ISSUE-002",
      "type": "tech_debt",
      "severity": "medium",
      "location": "src/billing/invoice.py",
      "description": "Cyclomatic complexity of 45 (SonarQube) in critical invoice generation.",
      "context": "Flagged by static analysis, verified as high-risk by Analysis Agent."
    },
    {
      "id": "ISSUE-003",
      "type": "discrepancy",
      "severity": "low",
      "description": "API Docs state /users returns V2 format, but code returns V1.",
      "location": "src/users/controller.py"
    }
  ]
}
```

---

## Operational Workflow

1.  **Initialize**:
    ```bash
    python autonomous_agent_demo.py --audit --project-dir ./legacy-app
    ```
2.  **Review**: User reviews `feature_list.json` and `issues.json`.
3.  **Plan**: User selects next steps:
    *   "Fix ISSUE-001 (SQL Injection)"
    *   "Refactor ISSUE-002 (Invoice Complexity)"
    *   "Add New Feature X (referencing EXIST-001 for auth)"
4.  **Execute**: Standard `IMPLEMENT -> REVIEW -> FIX` loop runs, but agents now have the `feature_list.json` context to guide them.

## Key Benefits
1.  **No Duplication**: Agents know what exists.
2.  **Safe Refactoring**: Agents know who depends on shared services.
3.  **Context-Aware Issues**: Pure static analysis is noisy; LLM agents filter it to "what actually matters for this feature."
4.  **No Human-in-the-Loop required for Audit**: Fully automated discovery pipeline.
