# Monitor Agent — Enterprise Edition

AI-powered website change monitoring with a real-time dashboard, structured diffing, visual diff, a Model Context Protocol (MCP) server, and a human-in-the-loop approval workflow.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

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
4. **Diff against the previous version** — line-by-line semantic diff plus an optional **visual screenshot diff**
5. **Alert you** by email or through integrations (Slack, Notion, GitHub, n8n, webhook) when the change score exceeds your threshold
6. **Ask for approval** before running risky actions, with a configurable per-site approval policy
7. **Show everything** in a live dashboard with a side-by-side diff viewer

---

## Key features

- **Natural-language setup** — describe *what* to watch; the LLM figures out the URL and elements.
- **Structured diffing** — line-by-line `difflib` comparison with a change score, added/removed/modified line counts, and severity classification.
- **Visual diff** — Playwright screenshots of each version with pixel-level difference detection (`core/visual/`).
- **Multi-agent pipeline** — Scout (scrape) → Analyst (classify) → Reporter (summarize) → Action (act) with an orchestrator and cost tracking (`core/agents/`, `core/orchestrator.py`).
- **Action handlers** — email, Slack, Notion, GitHub, n8n, and generic webhook, with encrypted per-site credentials.
- **Approval workflow** — human-in-the-loop approval for high-risk actions. Per-site policy: `never`, `high_risk` (default), or `always`, with an expiry TTL and pending-request notifications.
- **Workflow rules** — declarative rules (`core/workflow/engine.py`) that trigger on change signals.
- **MCP server** — exposes all six tools to external AI agents (Claude Desktop, Cursor, VS Code) over HTTP+SSE, with API-key auth, site-scoped calls, payload sanitization, and approval gating.
- **Real-time dashboard** — Next.js 16 UI with a live feed (SSE), KPI overview, site CRUD, and a side-by-side diff viewer.
- **Scheduling** — APScheduler reading cron expressions from the database (reloads every 10 min).

---

## System architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser / Client                          │
│                  Next.js 16 Dashboard (port 3000)                │
│  /overview  /sites  /sites/[id]  /activity  /login              │
└───────────┬──────────────────────────────────────┬───────────────┘
            │ REST + SSE                           │ MCP over HTTP+SSE
┌───────────▼──────────────────────────────────────▼───────────────┐
│                     FastAPI Backend (port 8000)                   │
│  /auth/*  /api/monitor/*  /api/integrations/*  /api/approvals/*  │
│  SSE stream                                  mcp (port 8001)     │
└──────┬───────────────┬───────────────────┬────────────────────────┘
       │               │                   │
┌──────▼──────┐ ┌──────▼───────┐ ┌─────────▼──────────────────────┐
│  SQLite DB  │ │ Orchestrator │ │           Action layer          │
│  (or PG)    │ │ core/orchestra│ │  registry → handlers:          │
│             │ │  tor.py       │ │  email, slack, notion, github, │
│  users      │ │               │ │  n8n, webhook                  │
│  sites      │ │ Scout →       │ │  └─ approvals (human-in-loop)  │
│  snapshots  │ │ Analyst →     │ │  └─ per-site token encryption  │
│  changes    │ │ Reporter →    │ └────────────────────────────────┘
│  approvals  │ │ Action        │
└─────────────┘ └───────────────┘
       ▲
┌──────┴──────────────────────────────────────────────────────────┐
│              APScheduler (src/scheduler_db.py)                   │
│  Reads cron schedule from DB, runs each site on its schedule     │
└──────────────────────────────────────────────────────────────────┘
```

### Project structure

```
monitor_agent/
├── api/                        # FastAPI application layer
│   ├── main.py                 # App entry point, CORS, lifespan
│   ├── deps.py                 # Dependency injection (DB session, auth)
│   ├── auth/                   # JWT auth (register/login)
│   └── routers/                # monitor, integrations, approvals
├── core/
│   ├── orchestrator.py         # Full monitoring cycle (Scout→Analyst→Reporter→Action)
│   ├── monitor_service.py      # Thin wrapper used by scheduler/API
│   ├── agents/                 # Scout, Analyst, Reporter, Action agents + events
│   ├── actions/                # Action registry + handlers (email, slack, notion,
│   │                           #   github, n8n, webhook)
│   ├── approvals/              # Human-in-the-loop approval service + notifier
│   ├── visual/                 # Screenshot provider, pixel diff, storage
│   ├── workflow/               # Declarative workflow rules engine
│   ├── entities/               # Entity extraction + correlation
│   ├── llm/                    # LLM router + cost tracker
│   └── security/               # Token encryption (master + per-site keys)
├── mcp/                        # Model Context Protocol server (port 8001)
├── db/                         # SQLAlchemy models + session
├── src/                        # Original modules
│   ├── modules/                # ai_agent (Groq), firecrawl_scraper,
│   │                           #   content_comparator, gmail_notifier
│   ├── scheduler.py            # Legacy YAML-based scheduler
│   └── scheduler_db.py         # DB-backed scheduler (cron from DB)
├── frontend/                   # Next.js 16 dashboard (vendored)
├── config/
│   ├── settings.py             # Environment variable loader
│   ├── sites.yaml              # Legacy: static site list (reference only)
│   └── .env                    # API keys (create from .env.example)
├── tests/                      # 250+ tests across all layers
├── requirements.txt            # Core dependencies
├── requirements-api.txt        # FastAPI + SQLAlchemy + JWT + encryption
├── docker-compose.yml          # Full-stack one-command setup
└── Dockerfile                  # API container
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

#### 4. MCP server (optional — expose tools to external AI agents)

```bash
export MCP_API_KEY=your-mcp-api-key-here
python -m mcp.main        # port 8001, SSE at /mcp/sse
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

# ── Security ────────────────────────────────────────────────────────
SECRET_KEY=change-me-in-production        # JWT signing + token encryption

# ── Optional ────────────────────────────────────────────────────────
DATABASE_URL=sqlite:///./monitor.db       # Switch to postgresql://... for prod
ENV=development
LOG_LEVEL=INFO
DEFAULT_CHANGE_THRESHOLD=1.0
GROQ_MODEL=mixtral-8x7b-32768
MCP_API_KEY=your-mcp-api-key-here         # Required to start the MCP server
APPROVAL_TTL_HOURS=24                     # Approval requests expire after N hours
N8N_WEBHOOK_URL=http://localhost:5678/webhook/monitor

# ── Legacy (only needed if using Google Sheets logging) ─────────────
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=your_sheet_id
```

> **Note:** `SECRET_KEY` is used both for JWT signing **and** for encrypting per-site
> integration tokens at rest. It must be set and non-empty — the app fails fast if
> it is missing. Use a strong, unique value in production.

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

Set an **alert threshold** (% change required to send an alert) and a **use case** tag.

### 3. Run a check

Click the **Play** button on any site card for an immediate check, or wait for the scheduler to run automatically based on the cron schedule.

### 4. View diffs

Click a site → **Change History** → select any detected change → see a side-by-side diff of exactly what changed between the two versions.

### 5. Live feed

The **Overview** page shows a real-time activity feed via Server-Sent Events — changes appear instantly without refreshing.

---

## Integrations

Configure per-site action credentials under **Integrations** in the dashboard (or via `PUT /api/integrations/sites/{id}`).

| Handler | Credential | What it does |
|---|---|---|
| Email | Gmail sender/recipient | HTML change alerts (default) |
| Slack | Webhook URL | Post change summaries to a channel |
| Notion | Integration token | Create a page per change |
| GitHub | Personal access token | Open an issue per change |
| n8n | Webhook URL | Trigger an n8n workflow |
| Webhook | URL + optional secret | POST a signed payload to any endpoint |

Credentials are **encrypted at rest** with a per-site key derived from `SECRET_KEY` (HMAC-SHA256), so one site's ciphertext cannot expose another's. The API only ever returns masked values.

Each site has an `actions_enabled` list (which handlers may fire) and an `integration_config` for handler-specific settings.

---

## Approval workflow

High-risk actions can require a human to approve them before they execute. This prevents automated pipelines from taking destructive or costly actions without review.

### Per-site policy

| Policy | Behavior |
|---|---|
| `never` | All actions run automatically |
| `high_risk` (default) | Actions with `risk_score >= 0.7` require approval |
| `always` | Every action requires approval |

When a run proposes an action that requires approval:

1. An `ApprovalRequest` is created with `status=pending`.
2. A notification (email + Slack, if configured) is sent summarizing the pending requests.
3. An admin (or the site owner) approves or rejects via the dashboard or `POST /api/approvals/{id}/approve`.
4. Pending requests older than `APPROVAL_TTL_HOURS` are lazily marked `expired`.

Approve calls claim the request with an atomic `pending → resolving` transition before executing the handler, so concurrent approvals cannot double-execute an action. Failed executions are recorded as `failed` (not `approved`) with the error surfaced in the API.

---

## MCP Server (Model Context Protocol)

The MCP server exposes all six action handlers (email, Slack, Notion, GitHub, n8n, webhook) to external AI agents (Claude Desktop, Cursor, VS Code) via the Model Context Protocol over HTTP+SSE.

### Start MCP Server

```bash
# Set API key (shared secret — required, the server fails fast if unset)
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

| Tool | Description |
|---|---|
| `email` | Send an email alert |
| `slack` | Post to a Slack webhook |
| `notion` | Create a Notion page |
| `github` | Create a GitHub issue |
| `n8n` | Trigger an n8n webhook |
| `webhook` | POST to a generic webhook |

Tool calls are **site-scoped**, run through the **same approval policy** as the scheduler (high-risk calls require approval), and client-supplied payload fields are **sanitized** against a per-handler allow-list — handler-derived values (e.g. the site's encrypted webhook) always take precedence.

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
| `GET` | `/api/integrations/sites/{id}` | Get site integrations (masked) |
| `PUT` | `/api/integrations/sites/{id}` | Update site integrations + credentials |
| `GET` | `/api/approvals` | List approval requests (filter by status) |
| `POST` | `/api/approvals/{id}/approve` | Approve + execute an action |
| `POST` | `/api/approvals/{id}/reject` | Reject an action |
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
python -m pytest -q
```

> The suite is hermetic — no live API keys or browsers needed. Run it with a fresh
> database (delete `monitor.db` once after upgrading if you get schema errors) and
> `MCP_API_KEY` set if you run the MCP tests: `MCP_API_KEY=x pytest -q`.
> CI runs the same command on every push (see `.github/workflows/ci.yml`).

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `SMTPAuthenticationError` | Wrong Gmail App Password | Regenerate at Google Account → Security → App Passwords |
| `google.auth.exceptions.DefaultCredentialsError` | Missing credentials.json | Download service account key from Google Cloud Console |
| Site URL shows `null` in dashboard | AI hasn't parsed it yet | Click **Run now** — Groq will resolve the URL on first check |
| Changes detected but diff is empty | Content changed but lines are identical | Dynamic content (ads, timestamps) — increase threshold |
| `bcrypt` warning on startup | passlib/bcrypt version mismatch | Ensure `bcrypt==4.0.1` is installed (pinned in requirements-api.txt) |
| `no such column: monitor_sites.<x>` | DB schema predates a recent version | Delete `monitor.db` — it is recreated automatically with the current schema |

---

## License

MIT — see [LICENSE](LICENSE)
