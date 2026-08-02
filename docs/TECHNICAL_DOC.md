# Monitor Agent — Technical Documentation

> Enterprise-grade web monitoring platform. FastAPI + Next.js + SQLAlchemy + APScheduler.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Database Schema](#3-database-schema)
4. [Backend — FastAPI](#4-backend--fastapi)
5. [Core Monitoring Service](#5-core-monitoring-service)
6. [Original Modules (Unchanged)](#6-original-modules-unchanged)
7. [DB-Backed Scheduler](#7-db-backed-scheduler)
8. [Authentication & JWT](#8-authentication--jwt)
9. [Server-Sent Events (SSE)](#9-server-sent-events-sse)
10. [Frontend — Next.js 16](#10-frontend--nextjs-16)
11. [Email Notifications](#11-email-notifications)
12. [Docker Deployment](#12-docker-deployment)
13. [Configuration Reference](#13-configuration-reference)
14. [API Endpoint Reference](#14-api-endpoint-reference)
15. [Data Flow — Full Monitoring Cycle](#15-data-flow--full-monitoring-cycle)
16. [Error Handling](#16-error-handling)
17. [Performance](#17-performance)
18. [Extension Guide](#18-extension-guide)

---

## 1. System Overview

Monitor Agent is an AI-powered website monitoring platform. Given a plain-English instruction ("Monitor competitor pricing on H&M"), it:

1. Parses the instruction with a Groq LLM to extract the URL and elements to watch
2. Scrapes the page with Firecrawl (handles JavaScript-heavy sites)
3. Stores full page content in a SQLite/PostgreSQL database
4. Diffs it against the previous version using Python difflib — line by line, not just hashes
5. Alerts by email if the change score exceeds the configured threshold
6. Streams all events in real time to a Next.js dashboard via SSE

### Key Fix vs. v1

The original `main.py` only stored MD5 hashes of page content and hardcoded `change_score = 5.0` for all "changes". Diffs were never real. The enterprise version fixes this by storing the full markdown content in `MonitorSnapshot.content_markdown`, enabling genuine line-by-line diffs.

---

## 2. Architecture

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
│  SQLite DB  │ │ core/monitor │  │    src/modules/ (unchanged) │
│  (or PG)   │ │  _service.py │  │  ai_agent     (Groq LLM)    │
│             │ │              │  │  firecrawl_scraper           │
│  sites      │ │  Orchestrates│  │  content_comparator          │
│  snapshots  │ │  the cycle   │  │  gmail_notifier              │
│  changes    │ └──────────────┘  └─────────────────────────────┘
│  users      │
│  notif_log  │
└─────────────┘
       ▲
┌──────┴──────────────────────────────────────────────────────────┐
│              APScheduler (src/scheduler_db.py)                   │
│  Reads cron schedule from DB, runs each site on its schedule     │
└──────────────────────────────────────────────────────────────────┘
```

### Agentic Core (Phase 1)

The monitoring cycle is now orchestrated by `MonitoringOrchestrator` in `core/orchestrator.py`:

```
Scout Agent → Analyst Agent → Reporter Agent → Action Agent
```

- **Scout Agent:** parses instructions, scrapes content, detects changes, extracts entities.
- **Analyst Agent:** runs semantic diff, classifies change type, assigns severity.
- **Reporter Agent:** drafts human-readable summaries.
- **Action Agent:** evaluates workflow rules, proposes actions, and enforces approval gates.

All agent decisions are recorded in `audit_logs`. High-risk actions create `approval_requests`.

### Project Structure

```
monitor_agent/
├── api/                        # FastAPI application layer
│   ├── main.py                 # App entry point, CORS, lifespan
│   ├── deps.py                 # Dependency injection (DB session, auth)
│   ├── auth/
│   │   ├── service.py          # JWT creation/verification, password hashing
│   │   └── router.py           # POST /auth/login, /auth/register
│   └── routers/
│       └── monitor.py          # All /api/monitor/* endpoints + SSE
├── db/                         # Database layer
│   ├── base.py                 # SQLAlchemy engine + session factory
│   └── models.py               # User, MonitorSite, MonitorSnapshot, MonitorChange
├── core/                       # Business logic
│   ├── monitor_service.py      # Delegates to MonitoringOrchestrator
│   ├── orchestrator.py         # Agentic pipeline orchestration
│   ├── agents/                 # Agent implementations
│   │   ├── events.py           # Typed agent event models
│   │   ├── scout.py            # Instruction parsing + scraping
│   │   ├── analyst.py          # Change classification
│   │   ├── reporter.py         # Summary generation
│   │   └── action.py           # Action execution + approval gating
│   ├── actions/                # Action handler plugin system
│   │   ├── base.py             # ActionHandler base classes
│   │   ├── registry.py         # Handler registry
│   │   └── handlers/           # Channel-specific handlers
│   │       ├── email.py
│   │       └── slack.py
│   ├── llm/                    # Multi-model LLM router
│   │   ├── config.py
│   │   ├── router.py
│   │   └── cost_tracker.py
│   ├── security/               # Token encryption
│   │   └── encryption.py
│   └── workflow/               # User-defined rule engine
│       └── engine.py
├── src/                        # Original modules (UNCHANGED)
│   ├── modules/
│   │   ├── ai_agent.py         # Groq LLM instruction parsing
│   │   ├── firecrawl_scraper.py# Web scraping (JS support)
│   │   ├── content_comparator.py # difflib change detection
│   │   ├── sheets_manager.py   # Legacy Google Sheets logging
│   │   └── gmail_notifier.py   # HTML email alerts
│   ├── scheduler.py            # Legacy YAML-based scheduler
│   └── scheduler_db.py         # DB-backed scheduler
├── config/
│   ├── settings.py             # Environment variable loader
│   ├── sites.yaml              # Legacy: static site list
│   └── .env                    # API keys (create from .env.example)
├── frontend/                   # Next.js 16 dashboard
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
├── docs/
│   └── TECHNICAL_DOC.md        # This file
├── requirements.txt            # Original Python dependencies
├── requirements-api.txt        # FastAPI + SQLAlchemy + JWT
├── docker-compose.yml          # Full-stack one-command setup
└── Dockerfile                  # API container
```

---

## 3. Database Schema

All tables use SQLAlchemy 2.0 mapped classes (`db/models.py`). SQLite by default; switch to PostgreSQL via `DATABASE_URL` environment variable.

### `users`

```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role            TEXT DEFAULT 'user',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `monitor_sites`

```sql
CREATE TABLE monitor_sites (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER REFERENCES users(id) ON DELETE CASCADE,
    instruction      TEXT NOT NULL,
    url              TEXT,                    -- resolved by AI Agent on first run
    threshold        REAL DEFAULT 1.0,        -- % change required to send alert
    schedule_cron    TEXT DEFAULT '0 */6 * * *',
    use_case         TEXT DEFAULT 'general',  -- ecommerce_pricing | regulatory | press | competitor
    tags             JSON DEFAULT '[]',
    active           BOOLEAN DEFAULT 1,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_checked_at  DATETIME,
    last_change_score REAL
);
```

### `monitor_snapshots`

```sql
CREATE TABLE monitor_snapshots (
    id               INTEGER PRIMARY KEY,
    site_id          INTEGER REFERENCES monitor_sites(id) ON DELETE CASCADE,
    scraped_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    content_markdown TEXT,     -- ← KEY FIX: stores full page content for real diffs
    content_hash     TEXT,     -- MD5 for quick equality check
    content_length   INTEGER,
    status           TEXT,     -- 'success' | 'error'
    error_message    TEXT
);
```

> **Why `content_markdown` matters**: Without storing full content, the comparator has nothing to diff. The v1 code stored only the hash — meaning every "diff" was a fabrication. This column is the fix.

### `monitor_changes`

```sql
CREATE TABLE monitor_changes (
    id               INTEGER PRIMARY KEY,
    site_id          INTEGER REFERENCES monitor_sites(id) ON DELETE CASCADE,
    detected_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    change_score     REAL,
    added_lines      INTEGER,
    removed_lines    INTEGER,
    modified_lines   INTEGER,
    diff_summary     TEXT,
    old_snapshot_id  INTEGER REFERENCES monitor_snapshots(id),
    new_snapshot_id  INTEGER REFERENCES monitor_snapshots(id),
    alert_sent       BOOLEAN DEFAULT 0
);
```

### `notification_log`

```sql
CREATE TABLE notification_log (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id),
    site_id    INTEGER REFERENCES monitor_sites(id),
    event_type TEXT,
    channel    TEXT DEFAULT 'email',
    sent_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    success    BOOLEAN
);
```

---

## 4. Backend — FastAPI

### Entry Point (`api/main.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()   # Creates all tables on first run
    yield

app = FastAPI(title="Monitor Agent API", lifespan=lifespan)

app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)          # /auth/*
app.include_router(monitor_router)       # /api/monitor/*
```

### Dependency Injection (`api/deps.py`)

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

### Database Engine (`db/base.py`)

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./monitor.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
```

---

## 5. Core Monitoring Service

`core/monitor_service.py` now delegates the full monitoring cycle to `MonitoringOrchestrator` in `core/orchestrator.py`. Called by the trigger endpoint and the scheduler.

### Function Signature

```python
def run_monitor_for_site(site: MonitorSite, db: Session) -> dict:
    """
    Returns:
        {
            "success": bool,
            "change_detected": bool,
            "change_score": float,
            "alert_sent": bool,
            "error": str | None,
            "run_id": str
        }
    """
```

### Agentic Pipeline

`MonitoringOrchestrator.run(site)` executes the following stages:

```
Step 1: Scout Agent
    parse_instruction(site.instruction)
    scrape_url(resolved_url)
    detect change vs previous snapshot
    extract entities (LLM-powered)
    → ScoutEvent

Step 2: Analyst Agent
    compare_content(old_md, new_md)
    classify change_type (price_drop, price_rise, new_product, content_update)
    assign severity (low, medium, high, critical)
    → AnalysisEvent

Step 3: Workflow Engine
    evaluate site.workflow_rules against AnalysisEvent
    → triggered actions

Step 4: Reporter Agent
    draft human-readable title + summary
    → ReportEvent

Step 5: Action Agent
    propose actions from registered handlers (email, slack, ...)
    execute low-risk actions
    create approval_requests for high-risk / "always" policy
    → ActionEvent

Persistence
    INSERT MonitorSnapshot (success or error)
    INSERT MonitorChange (when a change is detected)
    INSERT AuditLog (for every agent stage)
    INSERT ApprovalRequest (for gated actions)
```

---

## 6. Original Modules (Unchanged)

These modules in `src/modules/` are used as-is by `monitor_service.py`. They have not been modified.

### `ai_agent.py` — Instruction Parser

```python
class AIAgent:
    def parse_instruction(self, instruction: str) -> ParsedInstruction:
        """
        Input:  "Monitor prices on H&M men section"
        Output: ParsedInstruction(url="https://www2.hm.com/en_gb/men.html",
                                  elements_to_watch=["prices"])
        """
```

Uses Groq LLM (model: `GROQ_MODEL` env var, default `mixtral-8x7b-32768`) with few-shot prompting and Pydantic validation. Retries 3 times on JSON parse failure.

### `firecrawl_scraper.py` — Web Scraper

```python
class FirecrawlScraper:
    def scrape_url(self, url: str, max_retries: int = 3) -> ScrapedContent:
        """
        Returns: ScrapedContent(
            url, markdown, html,
            metadata=DocumentMetadata(title, description, language),
            success
        )
        """
```

Handles JavaScript-heavy pages. Retry strategy: 30s → 60s → 90s timeout.

### `content_comparator.py` — Diff Engine

```python
class ContentComparator:
    def compare_content(self,
        content_old: str,
        content_new: str,
        threshold: float = 1.0
    ) -> ComparisonResult:
```

Algorithm:
1. Normalize text (strip dynamic patterns: timestamps, session IDs, visitor counters)
2. `difflib.unified_diff()` for line-by-line diff
3. `difflib.SequenceMatcher()` for modified lines (similarity ≥ 0.7)
4. `change_score = (added + removed + modified) / total_lines * 100`

### `gmail_notifier.py` — Email Alerts

```python
class GmailNotifier:
    def send_notification(self, notification: ChangeNotification) -> bool:
```

HTML template with severity badges:
- **Normal** (< 5%): Blue
- **Moderate** (5–15%): Orange
- **Important** (15–30%): Red
- **Critical** (> 30%): Dark red

Uses Gmail SMTP on port 587 with TLS. Requires an App Password (not your main Google password).

---

## 7. DB-Backed Scheduler

`src/scheduler_db.py` reads sites from the database and schedules each one according to its `schedule_cron` field.

### How It Works

```python
def load_jobs(scheduler: BackgroundScheduler):
    db = SessionLocal()
    sites = db.query(MonitorSite).filter(MonitorSite.active == True).all()
    for site in sites:
        job_id = f"site_{site.id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        scheduler.add_job(
            check_site,
            CronTrigger.from_crontab(site.schedule_cron),
            args=[site.id],
            id=job_id,
        )
    db.close()
```

- `load_jobs()` runs every 10 minutes as a meta-job, so new sites added via API are picked up automatically.
- Each `check_site(site_id)` call opens its own DB session, runs `run_monitor_for_site()`, and closes the session.

### Cron Schedule Reference

| Schedule | Expression |
|---|---|
| Every hour | `0 * * * *` |
| Every 6 hours (default) | `0 */6 * * *` |
| Daily at 9am UTC | `0 9 * * *` |
| Twice daily (9am + 6pm) | `0 9,18 * * *` |
| Weekdays at 8am | `0 8 * * 1-5` |

---

## 8. Authentication & JWT

### Registration Flow

```
POST /auth/register  {"email": "...", "password": "..."}
→ hash_password(password) via bcrypt
→ INSERT INTO users
→ create_access_token({"sub": str(user.id)})
→ 201 {"access_token": "...", "token_type": "bearer"}
```

### Login Flow

```
POST /auth/login  (form data: username=email, password=...)
→ authenticate_user(email, password)
→ verify_password(plain, hashed) via bcrypt
→ create_access_token({"sub": str(user.id)})
→ 200 {"access_token": "...", "token_type": "bearer"}
```

### Token Verification

```python
def decode_token(token: str) -> Optional[dict]:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    if payload["exp"] < time.time():
        return None
    return payload
```

### Important: bcrypt Version

`bcrypt==4.0.1` is pinned in `requirements-api.txt`. Versions ≥ 4.1 removed `__about__.__version__` which passlib reads at import time, causing a `AttributeError` on startup. Do not upgrade without testing.

---

## 9. Server-Sent Events (SSE)

The dashboard uses SSE for real-time change notifications.

### Why Token as Query Param

Browser's native `EventSource` API cannot set custom headers. The JWT is passed as `?token=<jwt>` instead:

```typescript
// frontend/lib/api.ts
const token = localStorage.getItem("token");
const es = new EventSource(`${API_URL}/api/monitor/stream?token=${token}`);
```

### Server Implementation

```python
# In-memory subscriber registry
_sse_subscribers: dict[int, list[asyncio.Queue]] = {}

@router.get("/stream")
async def sse_stream(token: Optional[str] = None):
    # Manual auth (can't use Depends here — no headers)
    payload = decode_token(token)
    ...
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_subscribers.setdefault(user.id, []).append(queue)

    async def event_generator():
        yield 'data: {"type": "connected"}\n\n'
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"    # keep-alive, ignored by client

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Broadcasting

When a monitor run detects a change:

```python
_broadcast(user.id, {
    "type": "change_detected",
    "site_id": site_id,
    "change_score": result["change_score"],
    "alert_sent": result["alert_sent"],
    "timestamp": datetime.utcnow().isoformat(),
})
```

`_broadcast` puts the event into every queue for that `user_id`. Multiple browser tabs each get their own queue.

---

## 10. Frontend — Next.js 16

Built with Next.js 16 App Router, shadcn/ui (new-york style), Tailwind CSS v4, forced dark mode.

### Route Structure

```
app/
├── page.tsx                    → server redirect to /overview
├── (auth)/
│   └── login/
│       └── page.tsx            → login + register, redirects to /overview
└── (dashboard)/
    ├── layout.tsx              → sidebar nav + auth guard
    ├── overview/
    │   └── page.tsx            → KPI cards + live SSE feed
    ├── sites/
    │   ├── page.tsx            → sites list + Add Site dialog
    │   └── [id]/
    │       └── page.tsx        → change history + DiffViewer
    └── activity/
        └── page.tsx            → full paginated change log
```

### Auth Guard (Dashboard Layout)

```typescript
// app/(dashboard)/layout.tsx
useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) router.push("/login");
}, []);
```

### Typed API Client (`lib/api.ts`)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): HeadersInit {
    const token = localStorage.getItem("token");
    return { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" };
}

export const api = {
    getSites: (): Promise<Site[]> =>
        fetch(`${API_URL}/api/monitor/sites`, { headers: authHeaders() }).then(r => r.json()),

    triggerSite: (id: number) =>
        fetch(`${API_URL}/api/monitor/sites/${id}/trigger`, {
            method: "POST", headers: authHeaders()
        }),

    streamChanges: (onEvent: (e: SSEEvent) => void): EventSource => {
        const token = localStorage.getItem("token");
        const es = new EventSource(`${API_URL}/api/monitor/stream?token=${token}`);
        es.onmessage = (e) => onEvent(JSON.parse(e.data));
        return es;
    },
    // ... getDiff, getStats, createSite, deleteSite, etc.
};
```

### DiffViewer Component

Side-by-side table rendering old content (red background) vs new content (green background):

```tsx
// app/(dashboard)/sites/[id]/page.tsx
<table className="w-full font-mono text-xs">
  <thead>
    <tr>
      <th className="w-1/2 text-red-400">Previous</th>
      <th className="w-1/2 text-green-400">Current</th>
    </tr>
  </thead>
  <tbody>
    {oldLines.map((line, i) => (
      <tr key={i}>
        <td className="bg-red-950/30 px-2 py-0.5">{line}</td>
        <td className="bg-green-950/30 px-2 py-0.5">{newLines[i] ?? ""}</td>
      </tr>
    ))}
  </tbody>
</table>
```

### Fixing the Circular Font Bug

After `shadcn init`, `globals.css` emits `--font-sans: var(--font-sans)` — a circular reference that Tailwind v4's `@theme inline` resolves to nothing at parse time.

Fix:
```css
/* globals.css — inside @theme inline */
--font-sans: "Geist", "Geist Fallback", ui-sans-serif, system-ui, sans-serif;
--font-mono: "Geist Mono", "Geist Mono Fallback", ui-monospace, monospace;
```

---

## 11. Email Notifications

### Trigger Logic

In `monitor_service.py`:

```python
if result.change_score >= site.threshold:
    notification = ChangeNotification(
        url=site.url,
        instruction=site.instruction,
        change_score=result.change_score,
        added_lines=result.added_lines,
        removed_lines=result.removed_lines,
        modified_lines=result.modified_lines,
        diff_summary=result.diff_summary,
        threshold=site.threshold,
    )
    GmailNotifier().send_notification(notification)
```

### Required Gmail Setup

1. Enable 2-Step Verification on your Google Account
2. Go to **Security → App Passwords**
3. Create an app password for "Mail" on "Other"
4. Use the 16-character password as `GMAIL_APP_PASSWORD`

### SMTP Configuration

```
Server: smtp.gmail.com
Port:   587 (TLS/STARTTLS)
```

---

## 12. Docker Deployment

### Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `api` | `./Dockerfile` | 8000 | FastAPI + uvicorn |
| `scheduler` | `./Dockerfile` | — | Runs `python src/scheduler_db.py` |
| `frontend` | `./frontend/Dockerfile` | 3000 | Next.js standalone build |

Both `api` and `scheduler` share a `db_data` volume that holds the SQLite database at `/data/monitor.db`.

### Start

```bash
cp config/.env.example config/.env
# Edit config/.env

docker compose up
```

### Switching to PostgreSQL

Change `DATABASE_URL` in `docker-compose.yml`:

```yaml
environment:
  DATABASE_URL: postgresql://user:password@db:5432/monitor
```

Then add a `db` service:

```yaml
db:
  image: postgres:16
  environment:
    POSTGRES_USER: user
    POSTGRES_PASSWORD: password
    POSTGRES_DB: monitor
  volumes:
    - pg_data:/var/lib/postgresql/data
```

And update the `api` and `scheduler` services to `depends_on: db`.

---

## 13. Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✓ | — | Groq API key |
| `FIRECRAWL_API_KEY` | ✓ | — | Firecrawl API key |
| `GMAIL_SENDER_EMAIL` | ✓ | — | Gmail address to send from |
| `GMAIL_RECIPIENT_EMAIL` | ✓ | — | Alert destination email |
| `GMAIL_APP_PASSWORD` | ✓ | — | Gmail App Password (16 chars) |
| `SECRET_KEY` | ✓ | — | JWT signing secret (also used for token encryption) |
| `DATABASE_URL` | — | `sqlite:///./monitor.db` | SQLAlchemy DB URL |
| `ENV` | — | `development` | `development` or `production` |
| `LOG_LEVEL` | — | `INFO` | Python logging level |
| `DEFAULT_CHANGE_THRESHOLD` | — | `1.0` | Default % threshold for new sites |
| `GROQ_MODEL` | — | `mixtral-8x7b-32768` | Groq model to use |
| `LLM_ROUTER_CONFIG` | — | — | JSON string of multi-model router config |
| `GOOGLE_CREDENTIALS_FILE` | — | — | Legacy: service account JSON path |
| `GOOGLE_SHEET_ID` | — | — | Legacy: Google Sheets ID |

### Demo Seed Data

Pre-seeded for demo purposes (runs automatically at first startup if `ENV=demo`):

| Site | Instruction | Use case |
|---|---|---|
| 1 | Monitor pricing on H&M men's section | `ecommerce_pricing` |
| 2 | Track regulatory updates on EUR-Lex | `regulatory` |
| 3 | Watch for press releases on BBC News | `press` |

Demo credentials: `demo@monitor.ai` / `demo1234`

---

## 14. API Endpoint Reference

Base URL: `http://localhost:8000`

All `/api/monitor/*` endpoints require: `Authorization: Bearer <token>`

### Authentication

#### `POST /auth/register`

```json
// Request
{"email": "user@example.com", "password": "yourpassword"}

// Response 201
{"access_token": "eyJ...", "token_type": "bearer"}
```

#### `POST /auth/login`

```
Content-Type: application/x-www-form-urlencoded
Body: username=user@example.com&password=yourpassword

// Response 200
{"access_token": "eyJ...", "token_type": "bearer"}
```

### Sites

#### `GET /api/monitor/sites`

Returns all sites for the authenticated user.

```json
[
  {
    "id": 1,
    "instruction": "Monitor pricing on H&M men's section",
    "url": "https://www2.hm.com/en_gb/men.html",
    "threshold": 1.0,
    "schedule_cron": "0 */6 * * *",
    "use_case": "ecommerce_pricing",
    "tags": ["pricing", "ecommerce"],
    "active": true,
    "created_at": "2024-01-01T10:00:00",
    "last_checked_at": "2024-01-02T06:00:00",
    "last_change_score": 3.2
  }
]
```

#### `POST /api/monitor/sites`

```json
// Request
{
  "instruction": "Monitor pricing on H&M men's section",
  "threshold": 1.0,
  "schedule_cron": "0 */6 * * *",
  "use_case": "ecommerce_pricing",
  "tags": ["pricing"]
}

// Response 201 — same as SiteOut above
```

#### `PUT /api/monitor/sites/{id}`

Partial update. All fields optional:

```json
{"threshold": 2.5, "active": false, "schedule_cron": "0 9 * * 1-5"}
```

#### `DELETE /api/monitor/sites/{id}`

Returns `204 No Content`.

#### `POST /api/monitor/sites/{id}/trigger`

Runs a monitoring check immediately in a background task.

```json
// Response
{"status": "triggered", "site_id": 1}
```

#### `GET /api/monitor/sites/{id}/history?limit=20`

```json
{
  "site": { /* SiteOut */ },
  "snapshots": [
    {
      "id": 42,
      "scraped_at": "2024-01-02T06:00:00",
      "content_hash": "a1b2c3...",
      "content_length": 14523,
      "status": "success",
      "error_message": null
    }
  ],
  "changes": [
    {
      "id": 7,
      "detected_at": "2024-01-02T06:00:00",
      "change_score": 3.2,
      "added_lines": 12,
      "removed_lines": 8,
      "modified_lines": 3,
      "diff_summary": "Price changes in men's shirts section...",
      "alert_sent": true,
      "old_snapshot_id": 41,
      "new_snapshot_id": 42
    }
  ]
}
```

### Changes & Stats

#### `GET /api/monitor/changes?limit=50&skip=0`

Paginated list of all changes across all user's sites, newest first.

#### `GET /api/monitor/changes/{change_id}/diff`

```json
{
  "old_content": "# H&M Men\n\n## Shirts\n- Classic shirt £29.99\n...",
  "new_content": "# H&M Men\n\n## Shirts\n- Classic shirt £24.99\n...",
  "change_id": 7,
  "change_score": 3.2,
  "diff_summary": "Price change detected in shirts section"
}
```

#### `GET /api/monitor/stats`

```json
{
  "total_sites": 3,
  "active_sites": 3,
  "changes_this_week": 12,
  "alerts_sent_this_week": 5,
  "avg_change_score": 4.7,
  "use_case_breakdown": {
    "ecommerce_pricing": 1,
    "regulatory": 1,
    "press": 1
  }
}
```

#### `GET /api/monitor/stream?token=<jwt>`

SSE endpoint. Events:

```json
{"type": "connected"}
{"type": "change_detected", "site_id": 1, "change_score": 3.2, "alert_sent": true, "timestamp": "2024-01-02T06:00:00"}
```

#### `GET /health`

```json
{"status": "ok"}
```

---

## 15. Data Flow — Full Monitoring Cycle

```
User clicks "Run Now" in dashboard
        │
        ▼
POST /api/monitor/sites/{id}/trigger
        │
        ├── Returns immediately: {"status": "triggered"}
        │
        └── BackgroundTask: _run()
                │
                ▼
        core/monitor_service.py: run_monitor_for_site(site, db)
                │
                ▼
        core/orchestrator.py: MonitoringOrchestrator.run(site)
                │
                ├── 1. Scout Agent
                │       ├── AIAgent.parse_instruction(instruction) → url
                │       ├── FirecrawlScraper.scrape_url(url) → markdown
                │       ├── Hash check vs previous snapshot
                │       └── LLM entity extraction
                │
                ├── 2. Analyst Agent
                │       └── ContentComparator.compare_content(...) → change_type + severity
                │
                ├── 3. Workflow Engine
                │       └── evaluate site.workflow_rules
                │
                ├── 4. Reporter Agent
                │       └── draft title + summary
                │
                ├── 5. Action Agent
                │       ├── propose actions (email, slack, ...)
                │       ├── execute low-risk actions
                │       └── create approval_requests for gated actions
                │
                ├── 6. Persistence
                │       ├── INSERT MonitorSnapshot
                │       ├── INSERT MonitorChange
                │       ├── INSERT AuditLog (per stage)
                │       └── INSERT ApprovalRequest (if any)
                │
                └── 7. _broadcast(user_id, {type: "change_detected", run_id, ...})
                            │
                            ▼
                    SSE queue for each open browser tab
                            │
                            ▼
                    Dashboard live feed updates instantly
```

---

## 16. Error Handling

### Module Level

Each original module handles its own errors:

| Module | Strategy |
|---|---|
| `ai_agent.py` | 3 retries with JSON parse fallback; returns `ParsedInstruction(success=False)` |
| `firecrawl_scraper.py` | Exponential timeout (30→60→90s); returns `ScrapedContent(success=False)` |
| `gmail_notifier.py` | Logs SMTP error, returns `False`; workflow continues |

### Service Level

`monitor_service.py` wraps the full cycle:

```python
try:
    result = run_monitor_for_site(site, db)
except Exception as e:
    snapshot = MonitorSnapshot(site_id=site.id, status="error", error_message=str(e))
    db.add(snapshot); db.commit()
    return {"error": str(e), "change_detected": False}
```

### Common Errors

| Error | Cause | Fix |
|---|---|---|
| `SMTPAuthenticationError` | Wrong Gmail App Password | Regenerate at Google Account → Security → App Passwords |
| `bcrypt AttributeError` on startup | bcrypt version ≥ 4.1 | `pip install "bcrypt==4.0.1"` |
| Site URL shows `null` | AI hasn't parsed it yet | Click **Run Now** — Groq will resolve the URL on first check |
| `str \| None` SyntaxError | Python 3.9 doesn't support union type syntax | Use `Optional[str]` from `typing` |
| `Port 8000 already in use` | Old uvicorn process still running | `pkill -f "uvicorn api.main"` |

---

## 17. Performance

### Typical Execution Times per Site

| Operation | Typical | Notes |
|---|---|---|
| Instruction parsing (Groq) | 1–2s | LLM API call |
| Web scraping (Firecrawl) | 2–8s | Depends on page JS complexity |
| Hash check | < 1ms | Exits early if content unchanged |
| Diff computation (difflib) | < 100ms | Even for large pages |
| Email send (SMTP) | 1–3s | TLS handshake + send |
| **Total per site (change detected)** | **5–15s** | |
| **Total per site (no change)** | **4–11s** | No diff or email |

### Scaling Considerations

- **SQLite → PostgreSQL**: Set `DATABASE_URL=postgresql://...` — no code changes needed
- **Parallel site checks**: The scheduler runs each `check_site()` call sequentially per cron fire. For large numbers of sites, wrap with `ThreadPoolExecutor`
- **Content storage**: At ~50KB/snapshot × 1000 sites × 4 checks/day = ~200MB/day. Archive old snapshots with a scheduled cleanup job if needed

---

## 18. Extension Guide

### Add a New Notification Channel (e.g. Slack)

1. Create a handler in `core/actions/handlers/slack.py` implementing `ActionHandler`
2. Register it in `MonitoringOrchestrator.__init__`:
   ```python
   from core.actions.handlers.slack import SlackActionHandler
   self.action_registry.register(SlackActionHandler())
   ```
3. The handler's `propose()` should check `site.slack_webhook` and return a `ProposedAction`
4. The `ActionAgent` will automatically execute or gate the action based on `site.approval_policy`

### Add a New Use Case Tag

1. Add the tag string to the `use_case` values in the frontend `SiteCreate` dialog
2. The tag is stored as plain text — no backend change needed
3. Optionally add business logic in `monitor_service.py` that adjusts threshold behavior per use case

### Switch LLM Provider

The project uses the `core/llm/router.py` multi-model router. Add or override models via the `LLM_ROUTER_CONFIG` environment variable:

```json
{
  "openai_fast": {
    "provider": "openai_compatible",
    "base_url": "https://api.openai.com/v1",
    "api_env": "OPENAI_API_KEY",
    "model": "gpt-4o-mini"
  }
}
```

The router will read `OPENAI_API_KEY` from the environment and route `parse`/`report` tasks to the cheapest model and `vision` tasks to a vision-capable model.

### Add Alembic Migrations

Currently `init_db()` calls `Base.metadata.create_all()` which auto-creates tables but can't run migrations. For production:

```bash
pip install alembic
alembic init db/migrations
# Edit alembic.ini: sqlalchemy.url = ${DATABASE_URL}
# Edit env.py: from db.models import Base; target_metadata = Base.metadata
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

Replace `init_db()` call in `api/main.py` with the Alembic runner.

### Add Multi-Tenant Support Beyond Single User

The current schema is already multi-tenant: every `monitor_sites` row has `user_id`. To support organizations:

1. Add `Organization` model with `id, name, created_at`
2. Add `org_id` FK to `User`
3. Change API queries to filter by `org_id` instead of `user_id`
4. Add a role system (`admin`, `viewer`) to `User.role`
