# Agent WebUI Design

> Real-time web UI for monitoring autonomous coding agent sessions

---

## Overview

A 4-column grid interface displaying agent session outputs with live updates. Each column represents an agent type (IMPLEMENT, REVIEW, FIX, ARCHITECTURE). Rows represent iterations through the agent cycle, with one active cell per row.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (Vue 3 SPA)                      │
│  ┌───────────┬───────────┬───────────┬───────────┐              │
│  │ IMPLEMENT │  REVIEW   │    FIX    │ARCHITECTURE│             │
│  ├───────────┼───────────┼───────────┼───────────┤              │
│  │  Row 1    │           │           │           │  ← Session 1 │
│  │  Row 2    │  [active] │           │           │  ← Session 2 │
│  │  Row 3    │           │  [active] │           │  ← Session 3 │
│  └───────────┴───────────┴───────────┴───────────┘              │
└─────────────────────────────────────────────────────────────────┘
          │ SSE stream (live updates)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                               │
│  - GET /api/sessions → all session data                         │
│  - GET /api/stream   → SSE endpoint (file watcher)              │
└─────────────────────────────────────────────────────────────────┘
          │ reads
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Project Directory JSON Files                                    │
│  - progress.json (session history)                              │
│  - reviews.json (review verdicts/issues)                        │
│  - architecture_reviews.json                                    │
│  - feature_list.json                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow:**
1. Backend watches JSON files using `watchfiles` library
2. On change, parses and pushes update via SSE
3. Vue frontend receives update, re-renders affected cells

---

## Directory Structure

```
autonomous-coding/
├── webui/
│   ├── backend/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── routes.py            # API endpoints
│   │   ├── watcher.py           # File watcher + SSE logic
│   │   ├── parsers.py           # JSON file parsers
│   │   └── requirements.txt     # Python dependencies
│   │
│   ├── frontend/
│   │   ├── index.html           # Entry HTML
│   │   ├── src/
│   │   │   ├── App.vue          # Root component
│   │   │   ├── main.js          # Vue app bootstrap
│   │   │   ├── components/
│   │   │   │   ├── SessionGrid.vue
│   │   │   │   ├── AgentColumn.vue
│   │   │   │   ├── SessionCell.vue
│   │   │   │   └── ExpandableSection.vue
│   │   │   ├── composables/
│   │   │   │   └── useSSE.js
│   │   │   └── stores/
│   │   │       └── sessions.js
│   │   ├── package.json
│   │   └── vite.config.js
│   │
│   └── README.md
```

---

## Backend API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sessions` | Returns all session data merged from JSON files |
| `GET` | `/api/stream` | SSE endpoint - pushes updates on file changes |
| `GET` | `/api/health` | Health check |

### Session Data Shape

```json
{
  "project": {
    "name": "Project Name",
    "total_features": 50,
    "features_completed": 15
  },
  "rows": [
    {
      "row_id": 1,
      "timestamp": "2025-01-29T10:00:00Z",
      "agent_type": "IMPLEMENT",
      "session": {
        "session_id": 1,
        "outcome": "READY_FOR_REVIEW",
        "summary": "Implemented F001...",
        "features_touched": ["F001"],
        "commits": [{"hash": "abc123", "message": "..."}],
        "duration_seconds": 120
      },
      "structured_data": {
        "feature": {"id": "F001", "name": "Health Check", "passes": false}
      }
    },
    {
      "row_id": 2,
      "timestamp": "2025-01-29T10:30:00Z",
      "agent_type": "REVIEW",
      "session": { "..." : "..." },
      "structured_data": {
        "verdict": "REQUEST_CHANGES",
        "issues": {"critical": [], "major": ["..."], "minor": []},
        "checklist": {"functionality": "PASS", "testing": "FAIL"}
      }
    }
  ]
}
```

### SSE Event Format

```json
{
  "event": "update",
  "data": { "/* same shape as /api/sessions */" : "" }
}
```

---

## Frontend Components

### Component Hierarchy

```
App.vue
└── SessionGrid.vue
    ├── AgentColumn.vue (×4: IMPLEMENT, REVIEW, FIX, ARCHITECTURE)
    │   └── SessionCell.vue (×N rows)
    │       ├── ExpandableSection.vue (Structured Data - expanded)
    │       ├── ExpandableSection.vue (Session History - collapsed)
    │       └── ExpandableSection.vue (Console Output - collapsed)
```

### SessionCell States

| State | Appearance |
|-------|------------|
| Active (current agent) | Highlighted border, pulsing indicator |
| Completed | Normal styling, all sections available |
| Empty | Grayed out, no content for this agent in row |

### ExpandableSection Defaults

| Section | Default State | Content |
|---------|---------------|---------|
| Structured Data | **Expanded** | Feature info, review verdicts, issues, checklist |
| Session History | Collapsed | Timestamps, outcome, commits, summary |
| Console Output | Collapsed | Raw agent output (if captured) |

### Styling

- CSS Grid for 4-column layout
- Minimal dependencies (plain CSS, no frameworks)
- Dark/light mode via CSS variables

---

## Column Minimization

### Column States

| State | Width | Content |
|-------|-------|---------|
| Expanded | `1fr` (equal share) | Full cell content with expandable sections |
| Minimized | `48px` | Icon + agent name vertical, click to expand |

### Behavior

- Click column header to toggle minimize/expand
- Multiple columns can be minimized simultaneously
- Minimized columns show vertical label (rotated text)
- State persisted in localStorage
- Double-click header = expand this column, minimize all others (focus mode)

### Visual Example

```
┌────────────────────────────────────────────────────────┐
│ [−] IMPLEMENT  │ [−] REVIEW  │ [+] │ [+] │            │
│                │             │  F  │  A  │            │
│  Full content  │ Full content│  I  │  R  │            │
│  with cells    │ with cells  │  X  │  C  │            │
│                │             │     │  H  │            │
└────────────────────────────────────────────────────────┘
       ↑               ↑          ↑     ↑
   expanded        expanded   minimized minimized
```

---

## File Watcher & SSE

### Watched Files

```python
WATCHED_FILES = [
    "progress.json",
    "reviews.json",
    "architecture_reviews.json",
    "feature_list.json"
]
```

### Watcher Behavior

1. On startup, parse all files and build initial state
2. Use `watchfiles` library to detect changes
3. On change, re-parse affected file(s)
4. Push full state to all connected SSE clients

### SSE Connection Handling

| Event | Action |
|-------|--------|
| Client connects | Send full current state immediately |
| File changes | Broadcast update to all clients |
| Client disconnects | Remove from subscriber list |
| Parse error | Log error, keep last valid state |

### Project Directory Configuration

- Backend accepts `--project-dir` CLI argument
- Defaults to parent directory (`../`) assuming webui is inside autonomous-coding
- Example: `python main.py --project-dir /path/to/generated-project`

---

## Error Handling

### Backend Errors

| Error | Handling |
|-------|----------|
| JSON file missing | Return empty data for that source, log warning |
| JSON parse error | Keep last valid state, log error, notify via SSE |
| Project dir not found | Return 503 with clear error message |
| SSE connection lost | Client auto-reconnects (frontend logic) |

### Frontend Errors

| Error | Handling |
|-------|----------|
| SSE connection fails | Show reconnecting indicator, retry with backoff (1s, 2s, 4s, max 30s) |
| SSE reconnected | Show brief "Connected" toast, resume normal state |
| Invalid data received | Log to console, ignore malformed update |

### UI Status Indicators

```
┌─────────────────────────────────────────────────┐
│ 🟢 Connected  │  Project: MyApp  │  15/50 done  │
├─────────────────────────────────────────────────┤
│ ... grid content ...                            │
└─────────────────────────────────────────────────┘
```

Connection states:
- 🟢 Connected - SSE active
- 🟡 Reconnecting - SSE lost, retrying
- 🔴 Disconnected - Failed after max retries (manual refresh needed)

---

## Startup & Development

### Development Workflow

```bash
# Terminal 1 - Backend
cd autonomous-coding/webui/backend
pip install -r requirements.txt
python main.py --project-dir /path/to/generated-project

# Terminal 2 - Frontend
cd autonomous-coding/webui/frontend
npm install
npm run dev
```

### Ports

| Service | Port | URL |
|---------|------|-----|
| Backend (FastAPI) | 8000 | http://localhost:8000 |
| Frontend (Vite dev) | 5173 | http://localhost:5173 |

### Production Build

```bash
# Build frontend
cd frontend && npm run build

# Serve via FastAPI (static files)
# Backend serves built frontend from /frontend/dist
python main.py --project-dir /path/to/project
# Access at http://localhost:8000
```

### Dependencies

**Backend (`requirements.txt`):**
```
fastapi>=0.109.0
uvicorn>=0.27.0
watchfiles>=0.21.0
sse-starlette>=1.8.0
```

**Frontend (`package.json` key deps):**
```json
{
  "vue": "^3.4",
  "pinia": "^2.1",
  "vite": "^5.0"
}
```

---

## Tech Stack Summary

| Layer | Technology |
|-------|------------|
| Backend | FastAPI + watchfiles + sse-starlette |
| Frontend | Vue 3 + Pinia + Vite |
| Communication | Server-Sent Events |
| Data source | JSON files (progress.json, reviews.json, etc.) |

---

## Files to Create

| File | Purpose |
|------|---------|
| `webui/backend/main.py` | FastAPI app, CLI args, static serving |
| `webui/backend/routes.py` | API endpoint definitions |
| `webui/backend/watcher.py` | File watching + SSE broadcasting |
| `webui/backend/parsers.py` | JSON parsing + row assembly |
| `webui/backend/requirements.txt` | Python dependencies |
| `webui/frontend/src/App.vue` | Root with status bar |
| `webui/frontend/src/main.js` | Vue app bootstrap |
| `webui/frontend/src/components/SessionGrid.vue` | 4-column layout |
| `webui/frontend/src/components/AgentColumn.vue` | Single column with minimize |
| `webui/frontend/src/components/SessionCell.vue` | Expandable cell |
| `webui/frontend/src/components/ExpandableSection.vue` | Collapsible section |
| `webui/frontend/src/composables/useSSE.js` | SSE connection logic |
| `webui/frontend/src/stores/sessions.js` | Pinia store for state |
| `webui/frontend/package.json` | NPM dependencies |
| `webui/frontend/vite.config.js` | Vite configuration |
| `webui/frontend/index.html` | Entry HTML |
| `webui/README.md` | Setup instructions |
