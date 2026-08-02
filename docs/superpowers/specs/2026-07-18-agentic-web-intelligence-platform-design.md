# Agentic Web Intelligence Platform — Architecture Design

**Project:** Monitor Agent — 2026 Transformation  
**Date:** 2026-07-18  
**Status:** Approved — ready for implementation planning  
**Approach:** Monolith with internal agent boundaries + separate MCP service

---

## 1. Executive Summary

This document describes the evolution of the current Monitor Agent (FastAPI + Next.js + SQLAlchemy + APScheduler) into an **autonomous web intelligence platform**. The platform moves beyond simple change detection to a multi-agent system that scrapes, classifies, reports, and acts on web changes, with built-in governance, observability, and MCP interoperability.

The architecture is **evolutionary**: existing services, models, and deployment patterns are preserved and extended rather than replaced.

---

## 2. Design Principles

| # | Principle | Implication |
|---|---|---|
| 1 | **Evolution, not rewrite** | Reuse the FastAPI backend, Next.js dashboard, SQLAlchemy models, and Docker setup. Add agentic capabilities as new modules and services. |
| 2 | **Interface-first agents** | Every agent exposes a typed input/output contract so it can be extracted into its own service later without changing consumers. |
| 3 | **OpenAI-compatible abstraction** | The multi-model router supports any OpenAI-compatible endpoint (OpenAI, Groq, Together, vLLM, Ollama with OpenAI compatibility). |
| 4 | **Approval by default** | Any action with side effects requires explicit human approval unless explicitly configured otherwise. |
| 5 | **Observable everything** | Every scrape, LLM call, decision, and action emits a trace event with cost and latency. |

---

## 3. Service Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Clients                                     │
│  Next.js Dashboard (port 3000)        Claude/Cursor/VS Code (MCP)       │
└───────┬─────────────────────────────────────┬───────────────────────────┘
        │ REST + SSE                          │ MCP (stdio / SSE)
        ▼                                     ▼
┌──────────────────────────┐        ┌──────────────────────────┐
│   monitor-agent-api      │        │   monitor-agent-mcp      │
│   (FastAPI)              │◄──────►│   (separate service)     │
│   REST + auth + jobs     │        │   MCP tools adapter      │
└──────┬───────────────────┘        └──────────────────────────┘
       │
       │ owns
       ▼
┌─────────────────────────────────────────────────────────────────┐
│              monitor-agent-core (same Python process)            │
│                                                                  │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │  Scout  │──►│  Analyst │──►│ Reporter │──►│  Action  │      │
│  │  Agent  │   │  Agent   │   │  Agent   │   │  Agent   │      │
│  └─────────┘   └──────────┘   └──────────┘   └────┬─────┘      │
│       ▲                                           │             │
│       └───────────────────────────────────────────┘             │
│                   (feedback loop)                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Multi-Model Router  │  Visual Diff Engine  │  Workflow  │    │
│  │                      │                      │  Engine    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL (prod) / SQLite (dev)                               │
│  users │ monitor_sites │ monitor_snapshots │ monitor_changes    │
│  audit_logs │ approval_requests │ workflow_runs                 │
└─────────────────────────────────────────────────────────────────┘
       ▲
┌──────┴──────────────────────────────────────────────────────────┐
│  Scheduler (APScheduler) + async task queue (Celery/ARQ optional) │
│  Cron triggers, webhook triggers, event-driven checks             │
└───────────────────────────────────────────────────────────────────┘
```

### Service responsibilities

| Service | Responsibility |
|---|---|
| `monitor-agent-api` | Auth, REST API, SSE, orchestration, state machine for checks, approval queue. |
| `monitor-agent-mcp` | MCP protocol adapter; maps `monitor_url`, `get_change_history`, `compare_versions`, `execute_action` to internal API calls. |
| `monitor-agent-core` | Agent swarm, multi-model router, diff engines, workflow engine, action plugins. |
| `monitor-agent-scheduler` | Cron scheduler, webhook receiver, event triggers. |
| `postgres` | Relational state + audit log. |
| `nextjs-dashboard` | UI for sites, diffs, approvals, cost dashboard, audit explorer. |

---

## 4. Data Model & Storage

### Core schema extensions

We extend the existing SQLAlchemy models rather than replacing them.

#### `monitor_sites` (extended)

| Column | Type | Purpose |
|---|---|---|
| `monitor_mode` | `String` | `standard` \| `competitive` \| `seo` |
| `scrape_config` | `JSON` | selectors to watch, screenshot enabled, viewport, JS wait |
| `workflow_rules` | `JSON` | user-defined conditional rules |
| `approval_policy` | `String` | `always` \| `high_risk` \| `auto` |
| `slack_webhook` | `String` | optional Slack webhook URL |
| `notion_token` | `String` | encrypted Notion integration token |
| `github_token` | `String` | encrypted GitHub token |
| `n8n_webhook_url` | `String` | optional n8n webhook URL |

#### `monitor_snapshots` (extended)

| Column | Type | Purpose |
|---|---|---|
| `screenshot_path` | `String` | path to full-page screenshot (S3/MinIO) |
| `dom_json_path` | `String` | path to extracted DOM structure |
| `extracted_entities` | `JSON` | structured entities (prices, products, meta tags) |
| `model_calls` | `JSON` | LLM calls made during this scrape |

#### `monitor_changes` (extended)

| Column | Type | Purpose |
|---|---|---|
| `change_type` | `String` | `price_drop` \| `new_product` \| `layout_change` \| `content_update` \| `seo_change` |
| `severity` | `String` | `low` \| `medium` \| `high` \| `critical` |
| `visual_diff_path` | `String` | path to visual diff image |
| `vision_description` | `Text` | natural-language description from vision model |
| `agent_reasoning` | `JSON` | Analyst/Reporter reasoning traces |

### New tables

#### `audit_logs`

Append-only record of every agent decision.

| Column | Purpose |
|---|---|
| `run_id` | correlation ID for one monitoring cycle |
| `site_id`, `change_id` | foreign keys |
| `actor` | `scout` \| `analyst` \| `reporter` \| `action` \| `user` |
| `action` | what happened |
| `reasoning` | why it happened |
| `cost_usd` | API cost |
| `latency_ms` | elapsed time |

#### `approval_requests`

Human-in-the-loop queue.

| Column | Purpose |
|---|---|
| `run_id`, `change_id` | correlation keys |
| `action_type` | `slack_post` \| `github_pr` \| `purchase` \| `webhook` |
| `risk_score` | 0–1 |
| `payload` | proposed action JSON |
| `status` | `pending` \| `approved` \| `denied` \| `expired` |
| `user_id` | approver |

#### `workflow_runs`

Conditional workflow execution state.

| Column | Purpose |
|---|---|
| `run_id`, `site_id` | correlation keys |
| `trigger_event` | what started the run |
| `conditions` | evaluated rules |
| `actions_taken` | executed actions |
| `status` | `running` \| `completed` \| `failed` \| `awaiting_approval` |

### Storage backends

- **Object storage:** S3-compatible (MinIO for local dev, S3/R2 for production) for screenshots and visual diffs.
- **Structured data:** PostgreSQL in production; SQLite remains for local development.
- **Trace/observability:** OpenTelemetry collector → optionally LangSmith or Jaeger.

---

## 5. Agent Pipeline & Data Flow

### Agent event contract

Agents communicate via typed events, not direct method calls.

```python
class AgentEvent(BaseModel):
    run_id: str
    site_id: int
    stage: Literal["scout", "analyst", "reporter", "action"]
    payload: dict
    cost_usd: float
    latency_ms: float
    timestamp: datetime
```

### Pipeline stages

#### 1. Scout Agent

- **Input:** `MonitorSite`
- **Output:** `ScoutEvent`
- **Responsibilities:**
  - Parse natural language instruction into URL + elements using the multi-model router.
  - Scrape text, HTML, DOM, and screenshot.
  - Detect if content changed against the previous snapshot (hash check).
  - Extract structured entities (prices, products, meta tags).
  - Emit `ScoutEvent` with `has_change`, `snapshot_id`, `entities`, `screenshot_path`.

#### 2. Analyst Agent

- **Input:** `ScoutEvent`
- **Output:** `AnalysisEvent`
- **Responsibilities:**
  - Run semantic diff on text/markdown if content changed.
  - Run visual diff if screenshots exist.
  - Use a vision model to describe visual changes.
  - Classify change type and assign severity.
  - Emit `AnalysisEvent` with `change_type`, `severity`, `visual_diff_path`, `vision_description`, `semantic_diff_summary`.

#### 3. Reporter Agent

- **Input:** `AnalysisEvent`
- **Output:** `ReportEvent`
- **Responsibilities:**
  - Draft a human-readable summary combining semantic and visual findings.
  - Generate severity badge and recommended actions.
  - Emit `ReportEvent` with `title`, `summary`, `recommended_actions`.

#### 4. Action Agent

- **Input:** `ReportEvent`
- **Output:** `ActionEvent` or `ApprovalRequest`
- **Responsibilities:**
  - Evaluate `workflow_rules` against the change.
  - Propose concrete actions via the action handler registry.
  - Compute `risk_score` for each action.
  - If `risk_score` exceeds the threshold or approval policy is `always`, create an `ApprovalRequest` and stop.
  - If auto-approved, execute the action and emit `ActionEvent`.
  - Feed action results back to the Scout Agent for future behavior tuning.

### Orchestration

A new `MonitoringOrchestrator` class replaces the linear `run_monitor_for_site`. It:
1. Runs the pipeline.
2. Persists every `AgentEvent` to `audit_logs`.
3. Handles approval gates.
4. Updates the dashboard via SSE.

### Data flow

```
MonitorSite
   │
   ▼
┌────────────┐
│   Scout    │ ──► scrape + entity extraction + snapshot
│   Agent    │
└────┬───────┘
     │ ScoutEvent
     ▼
┌────────────┐
│  Analyst   │ ──► semantic diff + visual diff + classification
│   Agent    │
└────┬───────┘
     │ AnalysisEvent
     ▼
┌────────────┐
│  Reporter  │ ──► human-readable report
│   Agent    │
└────┬───────┘
     │ ReportEvent
     ▼
┌────────────┐
│   Action   │ ──► evaluate rules → propose actions
│   Agent    │ ──► approve? ──► execute
└────┬───────┘
     │ ActionEvent
     ▼
feedback loop ──► Scout Agent tuning
```

---

## 6. Multi-Model Routing

### Router design

A single `LLMRouter` wraps all LLM calls and supports any OpenAI-compatible endpoint plus local models via Ollama's `/v1/chat/completions` compatibility layer.

```python
class LLMRouter:
    def route(self, task: TaskProfile) -> ModelConfig: ...
    async def chat(self, messages, task_profile) -> LLMResponse: ...
```

### Task profiles

| Profile | Use case | Default model class |
|---|---|---|
| `parse` | Fast structured JSON extraction | local small model or fast cloud model |
| `analyze` | Complex reasoning, classification | strong cloud model |
| `vision` | Image understanding | vision-capable model |
| `report` | Long-form summarization | strong cloud model |
| `action` | Action proposal, code/PR generation | strong coding model |

### Example configuration

```yaml
models:
  local_parse:
    provider: openai_compatible
    base_url: http://ollama:11434/v1
    model: llama3.1:8b
    cost_input_per_1k: 0.0
    cost_output_per_1k: 0.0

  groq_fast:
    provider: openai_compatible
    base_url: https://api.groq.com/openai/v1
    api_env: GROQ_API_KEY      # name of the env var that holds the API key
    model: llama-3.3-70b-versatile

  openai_vision:
    provider: openai_compatible
    base_url: https://api.openai.com/v1
    api_env: OPENAI_API_KEY    # name of the env var that holds the API key
    model: gpt-4o
    supports_vision: true
```

Every call is logged with model name, token usage, cost, latency, and trace ID.

---

## 7. Visual & Semantic Diff

### Semantic diff

- Reuse and extend `ContentComparator`.
- Add semantic chunking before diffing (by headings, products, sections).
- Add entity-aware diff: detect price changes, stock changes, and new items.
- Keep dynamic-content filtering but make patterns configurable per site.

### Visual diff

#### Screenshot capture

- Primary: Firecrawl screenshot API if available.
- Fallback: Playwright full-page screenshot.
- Store in object storage; DB keeps the path.

#### Visual diff pipeline

1. Capture before/after screenshots.
2. Resize and align.
3. Run pixel-level diff with `pixelmatch` or Pillow.
4. Highlight changed regions.
5. Feed before/after + diff highlight to a vision model.
6. Vision model returns a natural-language description.

The output is stored in `monitor_changes.vision_description`.

---

## 8. MCP Server

### Service boundary

`monitor-agent-mcp` is a separate service that exposes the platform as an MCP server. It authenticates to the internal API using a service JWT. It has no direct database access.

### Exposed tools

| Tool | Description |
|---|---|
| `monitor_url(url, check_interval, alert_conditions)` | Register a new site or trigger a one-time check. |
| `get_change_history(url, limit)` | Return recent changes with summaries. |
| `compare_versions(url, timestamp_a, timestamp_b)` | Return semantic + visual diff between two snapshots. |
| `execute_action(monitor_id, action_type, params)` | Propose or execute an action; returns an approval request if needed. |
| `approve_action(request_id)` | Approve a pending action. |

For high-risk actions, `execute_action` returns a pending approval request. The MCP client (Claude/Cursor) can ask the user before calling `approve_action(request_id)`.

---

## 9. Workflows & Action Agent

### Workflow rules

User-defined rules are stored as JSON in `monitor_sites.workflow_rules` and evaluated by the Action Agent.

```json
{
  "rules": [
    {
      "id": "price_drop_20",
      "condition": "change_type == 'price_drop' and price_change_pct > 20",
      "actions": [
        {"type": "email", "priority": "high"},
        {"type": "notion", "database": "Wishlist", "map": {"title": "product.name", "price": "product.price"}},
        {"type": "slack", "channel": "#deals"}
      ]
    },
    {
      "id": "competitor_weekly_digest",
      "condition": "monitor_mode == 'competitive' and schedule == 'weekly'",
      "actions": [{"type": "slack", "channel": "#comp-intel", "format": "weekly_report"}]
    }
  ]
}
```

### Action handler interface

```python
class ActionHandler(ABC):
    name: str
    risk_score: float

    async def propose(self, context: ActionContext) -> ProposedAction: ...
    async def execute(self, proposed: ProposedAction) -> ActionResult: ...
```

### Built-in handlers

| Handler | Side effects | Risk score |
|---|---|---|
| `email` | Sends email | low |
| `slack` | Posts to Slack | medium |
| `notion` | Updates Notion DB | medium |
| `github_pr` | Creates GitHub PR | high |
| `n8n_webhook` | Calls n8n workflow | medium |
| `generic_webhook` | Calls arbitrary HTTP | medium |
| `purchase` | Triggers purchase workflow | high |

High-risk actions (`risk_score >= 0.7`) always create an `ApprovalRequest`. Medium-risk actions depend on the site's `approval_policy`.

### Feedback loop

Action results are stored in `audit_logs`. The Scout Agent can use historical patterns to adjust scraping frequency or focus.

---

## 10. Governance, Observability & Human-in-the-Loop

### Human-in-the-loop

- Every proposed action has a `risk_score` and a site-level `approval_policy`.
- Approval requests appear in the Next.js dashboard and can be sent via email/SMS.
- The MCP server surfaces pending approvals as tool results.
- Approval records are immutable and stored in `approval_requests`.

### Audit trail

`audit_logs` is append-only. Every row records:
- `run_id` for tracing a full monitoring cycle.
- `actor` (agent or user).
- `action` and `reasoning`.
- `cost_usd` and `latency_ms`.

Dashboard views:
- **Run timeline:** all events for one check.
- **Site audit:** all decisions for a site.
- **Cost dashboard:** spend by site, model, day.

### Observability

- **OpenTelemetry** traces for every agent call, LLM call, scrape, and action.
- **Metrics:** checks per minute, change detection rate, alert success rate, cost per check.
- **Optional LangSmith** integration for LLM-specific traces.
- **Health checks** on `/health` for each service.

---

## 11. Deployment & Security

### Docker Compose (local / small production)

Add to the existing `docker-compose.yml`:
- `postgres` service
- `mcp` service
- `minio` service for object storage
- `ollama` service (optional) for local models

### Kubernetes (production)

- Helm chart with deployments for `api`, `mcp`, `scheduler`.
- Horizontal Pod Autoscaler on the API.
- Secrets managed via Kubernetes Secrets or external secret manager.
- PostgreSQL and S3 as external dependencies.

### Security

- API keys and integration tokens encrypted at rest.
- Service-to-service authentication via JWT.
- MCP server authenticated separately; no direct DB access.
- All actions logged and approved by default.
- Rate limiting on public endpoints.

---

## 12. Implementation Phases

| Phase | Focus | Deliverables |
|---|---|---|
| **Phase 0: Foundation** | Multi-model router, audit log schema, cost tracking, approval framework. | `LLMRouter`, `audit_logs`, `approval_requests`, encrypted tokens. |
| **Phase 1: Agentic Core** | Refactor into Scout → Analyst → Reporter → Action pipeline; keep existing REST API working. | `MonitoringOrchestrator`, agent classes, `ActionHandler` registry, workflow rule evaluator. |
| **Phase 2: Visual & Semantic Diff** | Screenshots, visual diff, vision descriptions, entity extraction. | Screenshot storage, visual diff engine, `vision_description`, semantic chunking. |
| **Phase 3: MCP Server** | Standalone MCP service exposing the core tools. | `monitor-agent-mcp` service, service-to-service auth, approval-aware `execute_action`. |
| **Phase 4: Integrations** | Slack, Notion, GitHub PR, n8n, generic webhook handlers. | Plugin implementations, dashboard config UI. |
| **Phase 5: Competitive & SEO Modes** | Specialized monitoring modes and reports. | `monitor_mode` logic, weekly digest generator, SEO change tracking. |
| **Phase 6: Production Hardening** | OpenTelemetry, PostgreSQL migration path, K8s manifests, cost dashboard. | Helm chart, observability stack, dashboard cost views. |

### Recommended starting point

Start with **Phase 0 + Phase 1** together. They form the new backbone: the LLM router, audit trail, and agent pipeline. Once those are in place, visual diff, MCP, and integrations plug in cleanly.

---

## 13. Decision Log

| Decision | Rationale |
|---|---|
| Monolith with internal agent boundaries | Fastest path from current codebase; agents can be extracted later thanks to interface-first design. |
| Separate MCP service | Required by user; isolates protocol concerns; enables independent deployment. |
| OpenAI-compatible LLM abstraction | Supports both cloud (Groq, OpenAI, Together) and local (Ollama) models with one code path. |
| Approval-by-default | Aligns with governance requirements; high-risk actions always require human review. |
| PostgreSQL in production, SQLite in dev | Preserves existing dev simplicity; production-ready default. |
| S3-compatible object storage for screenshots | Decouples binary storage from the database; works with MinIO locally and S3/R2 in production. |

---

## 14. Open Questions for Implementation Planning

1. Which MCP transport should we implement first: `stdio` or `SSE`?
2. Which screenshot tool should be the primary: Firecrawl screenshot or Playwright?
3. Should workflow rules use a simple expression language (e.g., `expr`) or JSON-based conditions?
4. Which observability backend should be the default: Jaeger + Prometheus, or LangSmith?
5. Do we need multi-tenant organizations beyond the current `user_id` model?

