# Monitor Agent — Enterprise Edition

AI-powered website change monitoring with a real-time dashboard, structured diffing, and email alerts.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

---

## What it does

Monitor Agent watches any website for changes and tells you exactly what changed, when, and by how much — without you lifting a finger.

Give it a plain-English instruction:

> *"Monitor competitor pricing on H&M"*
> *"Track regulatory updates on EUR-Lex"*
> *"Watch for new press releases on BBC News"*

It will:
1. **Parse the instruction** with a Groq LLM to identify the URL and elements to watch
2. **Scrape the page** with Firecrawl (handles JavaScript-heavy sites)
3. **Store the full content** in a local database
4. **Diff against the previous version** using Python difflib — line by line, not just hashes
5. **Alert you by email** when the change score exceeds your threshold
6. **Show everything** in a live dashboard with a side-by-side diff viewer

---

## System architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser / Client                          │
│                  Next.js 16 Dashboard (port 3000)                │
│  /overview  /sites  /sites/[id]  /activity  /login              │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST + SSE
┌───────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                    │
│  /auth/*   /api/monitor/sites/*   /api/monitor/stream (SSE)      │
└──────┬───────────────┬────────────────────────┬──────────────────┘
       │               │                        │
┌──────▼──────┐ ┌──────▼───────┐  ┌────────────▼────────────────┐
│  SQLite DB  │ │ core/monitor │  │    Existing Python modules  │
│  (or PG)   │ │  _service.py │  │  ai_agent  (Groq LLM)       │
│             │ │              │  │  firecrawl_scraper          │
│  sites      │ │  Orchestrates│  │  content_comparator         │
│  snapshots  │ │  the 5       │  │  gmail_notifier             │
│  changes    │ │  modules     │  └─────────────────────────────┘
│  users      │ └──────────────┘
│  notif_log  │
└─────────────┘
       ▲
┌──────┴──────────────────────────────────────────────────────────┐
│              APScheduler (src/scheduler_db.py)                   │
│  Reads cron schedule from DB, runs each site on its schedule     │
└──────────────────────────────────────────────────────────────────┘
```

### Project structure

```
monitor_agent/
├── api/                        # FastAPI application layer (NEW)
│   ├── main.py                 # App entry point, CORS, lifespan
│   ├── deps.py                 # Dependency injection (DB session, auth)
│   ├── auth/
│   │   ├── service.py          # JWT creation/verification, password hashing
│   │   └── router.py           # POST /auth/login, /auth/register
│   └── routers/
│       └── monitor.py          # All /api/monitor/* endpoints + SSE
├── db/                         # Database layer (NEW)
│   ├── base.py                 # SQLAlchemy engine + session factory
│   └── models.py               # User, MonitorSite, MonitorSnapshot, MonitorChange
├── core/                       # Business logic (NEW)
│   └── monitor_service.py      # Full monitoring cycle — THE key fix vs. old code
├── src/                        # Original modules (UNCHANGED)
│   ├── modules/
│   │   ├── ai_agent.py         # Groq LLM instruction parsing
│   │   ├── firecrawl_scraper.py# Web scraping (JS support)
│   │   ├── content_comparator.py # difflib change detection
│   │   ├── sheets_manager.py   # Legacy Google Sheets logging
│   │   └── gmail_notifier.py   # HTML email alerts
│   ├── scheduler.py            # Legacy YAML-based scheduler (still works)
│   └── scheduler_db.py         # NEW: DB-backed scheduler
├── config/
│   ├── settings.py             # Environment variable loader
│   ├── sites.yaml              # Legacy: static site list
│   └── .env                    # API keys (create from .env.example)
├── frontend/                   # Next.js 16 dashboard (NEW)
│   ├── app/
│   │   ├── (auth)/login/       # Login / register
│   │   └── (dashboard)/
│   │       ├── overview/       # KPI cards + live feed
│   │       ├── sites/          # Sites list + CRUD
│   │       ├── sites/[id]/     # Site detail + diff viewer
│   │       └── activity/       # Full change log
│   └── lib/
│       ├── api.ts              # Typed API client
│       └── types.ts            # TypeScript interfaces
├── requirements.txt            # Original Python dependencies
├── requirements-api.txt        # NEW: FastAPI + SQLAlchemy + JWT
├── docker-compose.yml          # NEW: full-stack one-command setup
├── Dockerfile                  # NEW: API container
└── monitor.db                  # SQLite database (auto-created)
```

---

## Quickstart

### Option A — Docker (recommended, zero setup)

```bash
# 1. Copy and fill in your API keys
cp config/.env.example config/.env
# Edit config/.env with: GROQ_API_KEY, FIRECRAWL_API_KEY, GMAIL_*

# 2. Start everything
docker compose up

# Dashboard  → http://localhost:3000
# API        → http://localhost:8000
# API docs   → http://localhost:8000/docs
```

All three services start in the correct order: API → Scheduler → Frontend.

### Option B — Local development

#### 1. Python backend

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# .\venv\Scripts\activate         # Windows

# Install all dependencies
pip install -r requirements.txt -r requirements-api.txt

# Configure environment
cp config/.env.example config/.env
# Edit config/.env — minimum required: GROQ_API_KEY, FIRECRAWL_API_KEY, GMAIL_*

# Start the API server (creates monitor.db automatically on first run)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Next.js frontend

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
```

#### 3. Scheduler (optional — runs monitoring on cron schedules)

```bash
# In a separate terminal, with venv active:
python src/scheduler_db.py
```

#### 4. Legacy CLI (original behaviour, no dashboard)

```bash
# One-time run for all active sites in config/sites.yaml
python main.py

# Continuous scheduling from sites.yaml
python src/scheduler.py
```

---

## Environment variables

Create `config/.env` from `.env.example` and fill in:

```env
# ── Required ────────────────────────────────────────────────────────
GROQ_API_KEY=gsk_...                      # https://console.groq.com
FIRECRAWL_API_KEY=fc-...                  # https://firecrawl.dev
GMAIL_SENDER_EMAIL=you@gmail.com
GMAIL_RECIPIENT_EMAIL=alerts@yourco.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail → Security → App Passwords

# ── Optional ────────────────────────────────────────────────────────
SECRET_KEY=change-me-in-production        # JWT signing key
DATABASE_URL=sqlite:///./monitor.db       # Switch to postgresql://... for prod
ENV=development
LOG_LEVEL=INFO
DEFAULT_CHANGE_THRESHOLD=1.0
GROQ_MODEL=mixtral-8x7b-32768

# ── Legacy (only needed if using Google Sheets logging) ─────────────
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=your_sheet_id
```

---

## Using the dashboard

### 1. Create an account

Open `http://localhost:3000/login` → click **Sign up** → enter email + password.

### 2. Add a site

Go to **Sites** → **Add site** → describe what to monitor in plain English:

| Instruction example | Use case |
|---|---|
| `Monitor prices on hm.com men's section` | E-commerce pricing |
| `Watch for out-of-stock alerts on adidas.com` | E-commerce stock |
| `Track new directives on eur-lex.europa.eu` | Regulatory / compliance |
| `Monitor press releases on bbc.co.uk/news` | Press / media intelligence |
| `Watch competitor product launches on dyson.com` | Competitor intelligence |

Set an **alert threshold** (% change required to send an email) and a **use case** tag.

### 3. Run a check

Click the **Play** button on any site card for an immediate check, or wait for the scheduler to run automatically based on the cron schedule.

### 4. View diffs

Click a site → **Change History** → select any detected change → see a side-by-side diff of exactly what changed between the two versions.

### 5. Live feed

The **Overview** page shows a real-time activity feed via Server-Sent Events — changes appear instantly without refreshing.

---

## API reference

The full interactive API documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@co.com", "password": "yourpass"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -d "username=you@co.com&password=yourpass"

# Use the returned access_token as: Authorization: Bearer <token>
```

### Key endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Get JWT token |
| `GET` | `/api/monitor/sites` | List all your sites |
| `POST` | `/api/monitor/sites` | Add a new site |
| `PUT` | `/api/monitor/sites/{id}` | Update / pause a site |
| `DELETE` | `/api/monitor/sites/{id}` | Delete a site |
| `POST` | `/api/monitor/sites/{id}/trigger` | Run a check immediately |
| `GET` | `/api/monitor/sites/{id}/history` | Snapshots + change history |
| `GET` | `/api/monitor/changes/{id}/diff` | Full diff content for a change |
| `GET` | `/api/monitor/changes` | All changes (paginated) |
| `GET` | `/api/monitor/stats` | Aggregate KPIs |
| `GET` | `/api/monitor/stream?token=<jwt>` | SSE real-time event stream |
| `GET` | `/health` | Health check |

---

## Scheduling

Sites are scheduled using standard cron expressions stored in the database.

Default: `0 */6 * * *` (every 6 hours)

| Schedule | Cron expression |
|---|---|
| Every hour | `0 * * * *` |
| Every 6 hours | `0 */6 * * *` |
| Daily at 9am UTC | `0 9 * * *` |
| Twice daily | `0 9,18 * * *` |
| Weekdays at 8am | `0 8 * * 1-5` |

Update a site's schedule via the API:

```bash
curl -X PUT http://localhost:8000/api/monitor/sites/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"schedule_cron": "0 9 * * 1-5"}'
```

The scheduler (`src/scheduler_db.py`) reloads its job list every 10 minutes, so new sites added via the API are picked up automatically.

---

## Business use cases

### E-commerce clients

| Signal | Configuration |
|---|---|
| Competitor raises or lowers prices | `use_case: ecommerce_pricing`, threshold `1.0%` |
| Product goes out of stock | `use_case: ecommerce_stock`, threshold `0.5%` |
| New product launch | `use_case: competitor`, threshold `2.0%` |

**Measurable impact**: Detect a competitor price change 2–6 hours before it appears on price comparison engines. Respond before customers notice.

### Consulting clients

| Signal | Configuration |
|---|---|
| New EU regulation published | `use_case: regulatory`, threshold `0.5%` |
| Press release from tracked company | `use_case: press`, threshold `1.0%` |
| Market report updated | `use_case: competitor`, threshold `2.0%` |

**Measurable impact**: Regulatory alerts with full diff — exactly which paragraphs changed — without manually checking 20 sites per day.

---

## Running tests

```bash
source venv/bin/activate
pytest tests/ -v --cov=src
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `SMTPAuthenticationError` | Wrong Gmail App Password | Regenerate at Google Account → Security → App Passwords |
| `google.auth.exceptions.DefaultCredentialsError` | Missing credentials.json | Download service account key from Google Cloud Console |
| Site URL shows `null` in dashboard | AI hasn't parsed it yet | Click **Run now** — Groq will resolve the URL on first check |
| Changes detected but diff is empty | Content changed but lines are identical | Dynamic content (ads, timestamps) — increase threshold |
| `bcrypt` warning on startup | passlib/bcrypt version mismatch | Ensure `bcrypt==4.0.1` is installed (pinned in requirements-api.txt) |

---

## License

MIT — see [LICENSE](LICENSE)

---

## MCP Server (Model Context Protocol)

The MCP server exposes Monitor Agent's action handlers (email, Slack, Notion, GitHub, n8n, webhook) to external AI agents (Claude Desktop, Cursor, VS Code) via the Model Context Protocol over HTTP+SSE.

### Start MCP Server

```bash
# Set API key (shared secret)
export MCP_API_KEY=your-mcp-api-key-here

# Run directly
python -m mcp.main

# Or via docker-compose
docker compose up mcp
```

The server runs on port 8001 with SSE transport at `/mcp/sse`.

### MCP Client Configuration

For **Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "monitor-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8001/mcp/sse"],
      "env": {
        "MCP_API_KEY": "your-mcp-api-key-here"
      }
    }
  }
}
```

### Available Tools

| Tool | Description | Status |
|---|---|---|
| `email` | Send email alert | Implemented (stub) |
| `slack` | Post to Slack webhook | Implemented (stub) |
| `notion` | Create Notion page | Placeholder |
| `github` | Create GitHub issue | Placeholder |
| `n8n` | Trigger n8n webhook | Placeholder |
| `webhook` | Generic HTTP webhook | Placeholder |

Placeholders return `{"success": false, "message": "Not implemented"}` — real implementations coming in Phase 4.
