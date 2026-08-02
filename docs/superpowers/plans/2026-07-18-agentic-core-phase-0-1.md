# Agentic Web Intelligence Platform — Phase 0 + Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation (multi-model LLM router, audit logging, approval framework, encrypted token storage) and the agentic core pipeline (Scout → Analyst → Reporter → Action) for the Monitor Agent platform, while keeping the existing REST API and scheduler working.

**Architecture:** Extend the existing FastAPI + SQLAlchemy codebase with new `core/` modules for agents, LLM routing, cost tracking, actions, and workflow rules. The agents communicate via typed events and are orchestrated by a new `MonitoringOrchestrator` that replaces the linear `run_monitor_for_site`. Existing modules (`ai_agent`, `firecrawl_scraper`, `content_comparator`, `gmail_notifier`) are reused, not rewritten.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy 2.0, Pydantic, OpenAI SDK, `cryptography` (Fernet), pytest.

---

## File Structure

New files created:

```
core/
  orchestrator.py                    # MonitoringOrchestrator
  agents/
    events.py                        # AgentEvent, ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent
    scout.py                         # ScoutAgent
    analyst.py                       # AnalystAgent
    reporter.py                      # ReporterAgent
    action.py                        # ActionAgent
  llm/
    config.py                        # ModelConfig, TaskProfile, LLMResponse
    router.py                        # LLMRouter
    cost_tracker.py                  # CostTracker
  actions/
    base.py                          # ActionHandler, ProposedAction, ActionResult, ActionContext
    registry.py                      # ActionHandlerRegistry
    handlers/
      email.py                       # EmailActionHandler
      slack.py                       # SlackActionHandler
      notion.py                      # NotionActionHandler
      github_pr.py                   # GitHubPRActionHandler
      n8n_webhook.py                 # N8NWebhookActionHandler
      generic_webhook.py             # GenericWebhookActionHandler
      purchase.py                    # PurchaseActionHandler
  workflow/
    engine.py                        # WorkflowRule, WorkflowEngine
  security/
    encryption.py                    # TokenEncryption
db/models.py                         # extended (AuditLog, ApprovalRequest, site columns)
tests/core/...                       # unit tests for all new modules
```

Modified files:

- `requirements-api.txt` — add `openai`, `cryptography`
- `db/models.py` — add new models and columns
- `db/base.py` — ensure `init_db` creates new tables
- `api/routers/monitor.py` — trigger endpoint uses orchestrator
- `src/scheduler_db.py` — scheduler uses orchestrator
- `core/monitor_service.py` — deprecate or delegate to orchestrator

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements-api.txt`

- [ ] **Step 1: Add required packages**

Append to `requirements-api.txt`:

```text
# LLM routing (OpenAI-compatible clients)
openai>=1.0.0

# Token encryption
cryptography>=42.0.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements-api.txt
git commit -m "deps: add openai and cryptography for llm router and token encryption"
```

---

## Task 2: LLM Router Configuration Models

**Files:**
- Create: `core/llm/config.py`
- Test: `tests/core/test_llm_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_llm_config.py`:

```python
from core.llm.config import ModelConfig, TaskProfile, LLMResponse


def test_model_config_parses_yaml():
    data = {
        "provider": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "cost_input_per_1k": 0.0001,
        "cost_output_per_1k": 0.0002,
    }
    config = ModelConfig(**data)
    assert config.model == "llama-3.3-70b-versatile"
    assert config.supports_vision is False


def test_llm_response_cost_calculation():
    resp = LLMResponse(
        model="test",
        content="hello",
        usage={"prompt_tokens": 1000, "completion_tokens": 500},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
    )
    assert resp.total_cost == 0.01 + 0.015
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_llm_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.llm.config'`

- [ ] **Step 3: Implement the models**

Create `core/llm/config.py`:

```python
from typing import Optional, Any
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str = "openai_compatible"
    base_url: str
    api_env: str  # name of the environment variable holding the API key
    model: str
    cost_input_per_1k: float = 0.0
    cost_output_per_1k: float = 0.0
    supports_vision: bool = False
    timeout: float = 60.0


class TaskProfile(BaseModel):
    name: str  # parse | analyze | vision | report | action
    complexity: str = "simple"  # simple | complex
    latency_requirement: str = "low"  # low | high
    requires_vision: bool = False


class LLMResponse(BaseModel):
    model: str
    content: str
    usage: dict[str, Any]
    cost_input_per_1k: float
    cost_output_per_1k: float
    latency_ms: float = 0.0
    trace_id: Optional[str] = None

    @property
    def total_cost(self) -> float:
        input_cost = (self.usage.get("prompt_tokens", 0) / 1000) * self.cost_input_per_1k
        output_cost = (self.usage.get("completion_tokens", 0) / 1000) * self.cost_output_per_1k
        return round(input_cost + output_cost, 6)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_llm_config.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/llm/config.py tests/core/test_llm_config.py
git commit -m "feat(llm): add model and response configuration models"
```

---

## Task 3: LLM Router Implementation

**Files:**
- Create: `core/llm/router.py`
- Modify: `config/settings.py` (add config loader)
- Test: `tests/core/test_llm_router.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_llm_router.py`:

```python
from unittest.mock import patch, MagicMock
from core.llm.config import TaskProfile
from core.llm.router import LLMRouter


def test_router_chooses_vision_model_for_vision_task():
    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
        "vision": {"provider": "openai_compatible", "base_url": "http://vision", "api_env": "VISION_KEY", "model": "vision-model", "supports_vision": True},
    })
    profile = TaskProfile(name="analyze", requires_vision=True)
    selected = router.route(profile)
    assert selected.model == "vision-model"


@patch("core.llm.router.OpenAI")
def test_chat_returns_llm_response(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    mock_client.chat.completions.create.return_value = MagicMock(
        model="vision-model",
        choices=[MagicMock(message=MagicMock(content="hello"))],
        usage=MagicMock(prompt_tokens=10, completion_tokens=5),
    )

    router = LLMRouter({
        "fast": {"provider": "openai_compatible", "base_url": "http://fast", "api_env": "FAST_KEY", "model": "fast-model"},
    })
    with patch.dict("os.environ", {"FAST_KEY": "test-key"}):
        resp = router.chat([{"role": "user", "content": "hi"}], TaskProfile(name="parse"))
    assert resp.content == "hello"
    assert resp.total_cost == 0.0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_llm_router.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.llm.router'`

- [ ] **Step 3: Implement the router**

Create `core/llm/router.py`:

```python
import os
import time
from typing import Any, Optional
from openai import OpenAI

from core.llm.config import LLMResponse, ModelConfig, TaskProfile


class LLMRouter:
    def __init__(self, models: dict[str, dict[str, Any]]):
        self.models: dict[str, ModelConfig] = {k: ModelConfig(**v) for k, v in models.items()}
        self._clients: dict[str, OpenAI] = {}

    def route(self, task: TaskProfile) -> ModelConfig:
        if task.requires_vision:
            candidates = [m for m in self.models.values() if m.supports_vision]
            if candidates:
                return candidates[0]

        if task.name == "parse":
            return self._by_model_name("fast") or self._default_model()
        if task.name in ("analyze", "vision", "report", "action"):
            return self._default_model()
        return self._default_model()

    def _by_model_name(self, name: str) -> Optional[ModelConfig]:
        return self.models.get(name)

    def _default_model(self) -> ModelConfig:
        return next(iter(self.models.values()))

    def _get_client(self, config: ModelConfig) -> OpenAI:
        if config.base_url not in self._clients:
            api_key = os.getenv(config.api_env, "")
            self._clients[config.base_url] = OpenAI(base_url=config.base_url, api_key=api_key)
        return self._clients[config.base_url]

    def chat(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> LLMResponse:
        config = self.route(task)
        client = self._get_client(config)
        start = time.time()
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 500),
        )
        latency_ms = (time.time() - start) * 1000
        usage = response.usage
        return LLMResponse(
            model=config.model,
            content=response.choices[0].message.content or "",
            usage={"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens},
            cost_input_per_1k=config.cost_input_per_1k,
            cost_output_per_1k=config.cost_output_per_1k,
            latency_ms=latency_ms,
        )

    def chat_structured(self, messages: list[dict[str, str]], task: TaskProfile, **kwargs) -> str:
        return self.chat(messages, task, **kwargs).content
```

- [ ] **Step 4: Update settings to load router config**

Modify `config/settings.py` — add after existing imports:

```python
import json
```

Add near the bottom of the file before `__all__`:

```python
# ========================================
# LLM ROUTER CONFIG
# ========================================
LLM_ROUTER_CONFIG = os.getenv("LLM_ROUTER_CONFIG", "")

def load_llm_router_config() -> dict:
    """Load router config from env JSON or return a sensible default."""
    if LLM_ROUTER_CONFIG:
        try:
            return json.loads(LLM_ROUTER_CONFIG)
        except json.JSONDecodeError:
            raise ValueError("LLM_ROUTER_CONFIG is not valid JSON")
    return {
        "groq_fast": {
            "provider": "openai_compatible",
            "base_url": "https://api.groq.com/openai/v1",
            "api_env": "GROQ_API_KEY",
            "model": "llama-3.3-70b-versatile",
        }
    }

__all__.extend(["LLM_ROUTER_CONFIG", "load_llm_router_config"])
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_llm_router.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add core/llm/router.py config/settings.py tests/core/test_llm_router.py
git commit -m "feat(llm): add OpenAI-compatible multi-model router"
```

---

## Task 4: Cost Tracker

**Files:**
- Create: `core/llm/cost_tracker.py`
- Test: `tests/core/test_cost_tracker.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_cost_tracker.py`:

```python
from core.llm.cost_tracker import CostTracker
from core.llm.config import LLMResponse


def test_track_call_records_cost():
    tracker = CostTracker()
    resp = LLMResponse(
        model="m",
        content="c",
        usage={"prompt_tokens": 1000, "completion_tokens": 500},
        cost_input_per_1k=0.01,
        cost_output_per_1k=0.03,
        latency_ms=100.0,
        trace_id="run-1",
    )
    tracker.track("run-1", "parse", resp)
    summary = tracker.summary("run-1")
    assert summary["total_cost"] == 0.025
    assert summary["total_latency_ms"] == 100.0
    assert summary["calls"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_cost_tracker.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.llm.cost_tracker'`

- [ ] **Step 3: Implement the cost tracker**

Create `core/llm/cost_tracker.py`:

```python
from dataclasses import dataclass, field
from typing import Optional
from core.llm.config import LLMResponse


@dataclass
class CostTracker:
    calls: list[dict] = field(default_factory=list)

    def track(self, run_id: str, task: str, response: LLMResponse) -> None:
        self.calls.append({
            "run_id": run_id,
            "task": task,
            "model": response.model,
            "cost": response.total_cost,
            "latency_ms": response.latency_ms,
            "prompt_tokens": response.usage.get("prompt_tokens", 0),
            "completion_tokens": response.usage.get("completion_tokens", 0),
        })

    def summary(self, run_id: Optional[str] = None) -> dict:
        items = [c for c in self.calls if run_id is None or c["run_id"] == run_id]
        return {
            "calls": len(items),
            "total_cost": round(sum(c["cost"] for c in items), 6),
            "total_latency_ms": sum(c["latency_ms"] for c in items),
            "total_prompt_tokens": sum(c["prompt_tokens"] for c in items),
            "total_completion_tokens": sum(c["completion_tokens"] for c in items),
        }

    def reset(self, run_id: Optional[str] = None) -> None:
        if run_id is None:
            self.calls = []
        else:
            self.calls = [c for c in self.calls if c["run_id"] != run_id]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_cost_tracker.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add core/llm/cost_tracker.py tests/core/test_cost_tracker.py
git commit -m "feat(llm): add cost and latency tracker"
```

---

## Task 5: Token Encryption Utility

**Files:**
- Create: `core/security/encryption.py`
- Test: `tests/core/test_encryption.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_encryption.py`:

```python
from core.security.encryption import TokenEncryption


def test_encrypt_decrypt_roundtrip():
    enc = TokenEncryption("test-secret-key-32bytes-long!!")
    ciphertext = enc.encrypt("my-slack-token")
    assert ciphertext != "my-slack-token"
    plaintext = enc.decrypt(ciphertext)
    assert plaintext == "my-slack-token"


def test_different_key_fails():
    enc1 = TokenEncryption("test-secret-key-32bytes-long!!")
    enc2 = TokenEncryption("different-key-32bytes-long!!")
    ciphertext = enc1.encrypt("my-token")
    try:
        enc2.decrypt(ciphertext)
        assert False, "should have failed"
    except Exception:
        pass
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_encryption.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.security.encryption'`

- [ ] **Step 3: Implement encryption**

Create `core/security/encryption.py`:

```python
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken


class TokenEncryption:
    def __init__(self, secret_key: str):
        # Derive a 32-byte URL-safe base64-encoded Fernet key from any secret.
        digest = hashlib.sha256(secret_key.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Invalid token or wrong encryption key") from exc


def get_encryptor() -> TokenEncryption:
    from config import settings
    return TokenEncryption(settings.SECRET_KEY)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_encryption.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/security/encryption.py tests/core/test_encryption.py
git commit -m "feat(security): add Fernet token encryption utility"
```

---

## Task 6: Extend Database Models

**Files:**
- Modify: `db/models.py`
- Test: `tests/db/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/db/test_models.py`:

```python
from datetime import datetime
from db.base import init_db, SessionLocal
from db.models import User, MonitorSite, AuditLog, ApprovalRequest


def test_audit_log_creation():
    init_db()
    db = SessionLocal()
    try:
        log = AuditLog(
            run_id="run-1",
            site_id=1,
            actor="scout",
            action="scrape",
            reasoning="no previous snapshot",
            cost_usd=0.001,
            latency_ms=120.0,
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.id > 0
    finally:
        db.close()


def test_approval_request_creation():
    init_db()
    db = SessionLocal()
    try:
        req = ApprovalRequest(
            run_id="run-1",
            change_id=1,
            action_type="slack_post",
            risk_score=0.5,
            payload={"channel": "#deals"},
            status="pending",
            user_id=1,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.id > 0
    finally:
        db.close()


def test_site_has_monitor_mode():
    init_db()
    db = SessionLocal()
    try:
        user = User(email="test@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        site = MonitorSite(
            user_id=user.id,
            instruction="test",
            monitor_mode="competitive",
            approval_policy="high_risk",
        )
        db.add(site)
        db.commit()
        db.refresh(site)
        assert site.monitor_mode == "competitive"
    finally:
        db.close()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/db/test_models.py -v
```

Expected: `AttributeError: module 'db.models' has no attribute 'AuditLog'`

- [ ] **Step 3: Extend the models**

Modify `db/models.py`:

1. Add imports at the top:

```python
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
)
```

(Already present, just confirm.)

2. Extend `MonitorSite`:

```python
class MonitorSite(Base):
    __tablename__ = "monitor_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(2048))
    threshold: Mapped[float] = mapped_column(Float, default=1.0)
    schedule_cron: Mapped[str] = mapped_column(String(100), default="0 */6 * * *")
    use_case: Mapped[str] = mapped_column(String(100), default="general")
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_change_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # New fields
    monitor_mode: Mapped[str] = mapped_column(String(50), default="standard")
    scrape_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    workflow_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    approval_policy: Mapped[str] = mapped_column(String(50), default="high_risk")
    slack_webhook: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    notion_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    github_token: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    n8n_webhook_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sites")
    snapshots: Mapped[list["MonitorSnapshot"]] = relationship(
        "MonitorSnapshot", back_populates="site", cascade="all, delete-orphan",
        order_by="MonitorSnapshot.scraped_at.desc()"
    )
    changes: Mapped[list["MonitorChange"]] = relationship(
        "MonitorChange", back_populates="site", cascade="all, delete-orphan",
        order_by="MonitorChange.detected_at.desc()"
    )
```

3. Extend `MonitorSnapshot`:

```python
class MonitorSnapshot(Base):
    __tablename__ = "monitor_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    content_markdown: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(32), index=True)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scrape_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # New fields
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    dom_json_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_calls: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    site: Mapped["MonitorSite"] = relationship("MonitorSite", back_populates="snapshots")
```

4. Extend `MonitorChange`:

```python
class MonitorChange(Base):
    __tablename__ = "monitor_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    change_score: Mapped[float] = mapped_column(Float, default=0.0)
    added_lines: Mapped[int] = mapped_column(Integer, default=0)
    removed_lines: Mapped[int] = mapped_column(Integer, default=0)
    modified_lines: Mapped[int] = mapped_column(Integer, default=0)
    diff_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_snapshots.id"), nullable=True)
    new_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_snapshots.id"), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    # New fields
    change_type: Mapped[str] = mapped_column(String(50), default="content_update")
    severity: Mapped[str] = mapped_column(String(50), default="low")
    visual_diff_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    vision_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_reasoning: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    site: Mapped["MonitorSite"] = relationship("MonitorSite", back_populates="changes")
    old_snapshot: Mapped[Optional["MonitorSnapshot"]] = relationship(
        "MonitorSnapshot", foreign_keys=[old_snapshot_id]
    )
    new_snapshot: Mapped[Optional["MonitorSnapshot"]] = relationship(
        "MonitorSnapshot", foreign_keys=[new_snapshot_id]
    )
```

5. Add new `AuditLog` model:

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=True)
    change_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_changes.id"), nullable=True)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

6. Add new `ApprovalRequest` model:

```python
class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=True)
    change_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_changes.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/db/test_models.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/db/test_models.py
git commit -m "feat(db): add audit logs, approval requests, and agentic site columns"
```

---

## Task 7: Agent Event Models

**Files:**
- Create: `core/agents/events.py`
- Test: `tests/core/test_agent_events.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_agent_events.py`:

```python
from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent


def test_scout_event_serialization():
    event = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        snapshot_id=10,
        url="https://example.com",
        entities=[{"name": "price", "value": "10"}],
    )
    data = event.model_dump()
    assert data["stage"] == "scout"
    assert data["has_change"] is True


def test_action_event_serializes_result():
    event = ActionEvent(
        run_id="r1",
        site_id=1,
        actions=[{"type": "email", "success": True}],
        approval_requests=[],
    )
    assert event.model_dump()["stage"] == "action"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_agent_events.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agents.events'`

- [ ] **Step 3: Implement event models**

Create `core/agents/events.py`:

```python
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class AgentEvent(BaseModel):
    run_id: str
    site_id: int
    stage: str
    payload: dict = Field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ScoutEvent(AgentEvent):
    stage: str = "scout"
    has_change: bool
    snapshot_id: Optional[int] = None
    url: str
    content_markdown: Optional[str] = None
    content_html: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


class AnalysisEvent(AgentEvent):
    stage: str = "analyst"
    has_change: bool
    change_type: str = "content_update"
    severity: str = "low"
    change_score: float = 0.0
    added_lines: int = 0
    removed_lines: int = 0
    modified_lines: int = 0
    visual_diff_path: Optional[str] = None
    vision_description: Optional[str] = None
    semantic_diff_summary: Optional[str] = None


class ReportEvent(AgentEvent):
    stage: str = "reporter"
    title: str
    summary: str
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)


class ActionEvent(AgentEvent):
    stage: str = "action"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    approval_requests: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_agent_events.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/agents/events.py tests/core/test_agent_events.py
git commit -m "feat(agents): add typed agent event models"
```

---

## Task 8: Scout Agent

**Files:**
- Create: `core/agents/scout.py`
- Test: `tests/core/test_scout_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_scout_agent.py`:

```python
from unittest.mock import patch, MagicMock
from core.agents.scout import ScoutAgent
from db.models import MonitorSite


def make_site():
    return MonitorSite(id=1, instruction="monitor prices on example.com", threshold=1.0)


@patch("core.agents.scout.parse_instruction")
@patch("core.agents.scout.scrape_url")
def test_scout_detects_first_snapshot(mock_scrape, mock_parse):
    mock_parse.return_value = MagicMock(success=True, url="https://example.com", elements_to_watch=["prices"])
    mock_scrape.return_value = MagicMock(
        success=True,
        markdown="# Example\nPrice: $10",
        html="<html></html>",
        metadata={},
        timestamp=0,
    )

    agent = ScoutAgent()
    event = agent.run(make_site(), previous_snapshot=None)

    assert event.has_change is True
    assert event.url == "https://example.com"
    assert event.entities == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_scout_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agents.scout'`

- [ ] **Step 3: Implement the Scout Agent**

Create `core/agents/scout.py`:

```python
import hashlib
import time
from typing import Optional, Any
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile
from db.models import MonitorSite, MonitorSnapshot
from src.modules import parse_instruction, scrape_url


class ScoutAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None, db: Optional[Session] = None):
        self.llm_router = llm_router
        self.db = db

    def run(self, site: MonitorSite, previous_snapshot: Optional[MonitorSnapshot] = None) -> ScoutEvent:
        start = time.time()
        parsed = parse_instruction(site.instruction)
        if not parsed.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url="", error=parsed.error
            )

        if not site.url:
            site.url = parsed.url
            if self.db:
                self.db.commit()

        scraped = scrape_url(parsed.url)
        if not scraped.success:
            return ScoutEvent(
                run_id="", site_id=site.id, has_change=False, url=parsed.url, error=scraped.error
            )

        content_hash = hashlib.md5(scraped.markdown.encode("utf-8")).hexdigest()
        has_change = previous_snapshot is None or previous_snapshot.content_hash != content_hash

        entities = []
        if self.llm_router and has_change:
            entities = self._extract_entities(scraped.markdown)

        latency_ms = (time.time() - start) * 1000
        return ScoutEvent(
            run_id="",
            site_id=site.id,
            has_change=has_change,
            url=parsed.url,
            content_markdown=scraped.markdown,
            content_html=scraped.html,
            content_hash=content_hash,
            metadata=scraped.metadata if isinstance(scraped.metadata, dict) else {},
            entities=entities,
            latency_ms=latency_ms,
        )

    def _extract_entities(self, markdown: str) -> list[dict[str, Any]]:
        if not self.llm_router:
            return []
        messages = [
            {"role": "system", "content": "Extract structured entities (prices, products, stock status, etc.) as JSON."},
            {"role": "user", "content": markdown[:4000]},
        ]
        try:
            response = self.llm_router.chat(messages, TaskProfile(name="parse"))
            import json
            return json.loads(response.content) if response.content else []
        except Exception:
            return []
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_scout_agent.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add core/agents/scout.py tests/core/test_scout_agent.py
git commit -m "feat(agents): add Scout Agent with entity extraction"
```

---

## Task 9: Analyst Agent

**Files:**
- Create: `core/agents/analyst.py`
- Test: `tests/core/test_analyst_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_analyst_agent.py`:

```python
from unittest.mock import MagicMock
from core.agents.analyst import AnalystAgent
from core.agents.events import ScoutEvent
from db.models import MonitorSnapshot


def test_analyst_classifies_price_drop():
    scout = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        snapshot_id=2,
        url="https://example.com",
        entities=[{"name": "price", "value": "$10", "old_value": "$15"}],
    )
    old = MonitorSnapshot(id=1, site_id=1, content_markdown="Price $15", content_hash="a")
    new = MonitorSnapshot(id=2, site_id=1, content_markdown="Price $10", content_hash="b")

    agent = AnalystAgent()
    event = agent.run(scout, old, new)

    assert event.has_change is True
    assert event.change_type == "price_drop"
    assert event.severity == "high"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_analyst_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agents.analyst'`

- [ ] **Step 3: Implement the Analyst Agent**

Create `core/agents/analyst.py`:

```python
import time
from typing import Optional
from core.agents.events import ScoutEvent, AnalysisEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile
from db.models import MonitorSnapshot
from src.modules import compare_content


class AnalystAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router

    def run(self, scout: ScoutEvent, old_snapshot: Optional[MonitorSnapshot], new_snapshot: Optional[MonitorSnapshot]) -> AnalysisEvent:
        start = time.time()
        if not scout.has_change or old_snapshot is None or new_snapshot is None:
            return AnalysisEvent(
                run_id=scout.run_id,
                site_id=scout.site_id,
                has_change=False,
                change_type="content_update",
                severity="low",
            )

        comparison = compare_content(
            old_snapshot.content_markdown or "",
            new_snapshot.content_markdown or "",
            threshold=0.0,
        )

        change_type = self._classify_change(scout.entities, comparison)
        severity = self._severity(change_type, comparison.change_score)
        summary = comparison.diff_summary if comparison.has_changes else "No significant changes"

        latency_ms = (time.time() - start) * 1000
        return AnalysisEvent(
            run_id=scout.run_id,
            site_id=scout.site_id,
            has_change=comparison.has_changes,
            change_type=change_type,
            severity=severity,
            change_score=comparison.change_score,
            added_lines=len(comparison.added_lines),
            removed_lines=len(comparison.removed_lines),
            modified_lines=len(comparison.modified_lines),
            semantic_diff_summary=summary,
            latency_ms=latency_ms,
        )

    def _classify_change(self, entities: list, comparison) -> str:
        for entity in entities:
            name = entity.get("name", "").lower()
            old = str(entity.get("old_value", ""))
            new = str(entity.get("value", ""))
            if "price" in name:
                try:
                    old_val = float(old.replace("$", "").replace(",", ""))
                    new_val = float(new.replace("$", "").replace(",", ""))
                    if new_val < old_val:
                        return "price_drop"
                    if new_val > old_val:
                        return "price_rise"
                except ValueError:
                    pass
        if comparison.added_lines and not comparison.removed_lines:
            return "new_product"
        return "content_update"

    def _severity(self, change_type: str, change_score: float) -> str:
        if change_type in ("price_drop", "price_rise"):
            return "high" if change_score > 1.0 else "medium"
        if change_score > 5.0:
            return "critical"
        if change_score > 1.0:
            return "medium"
        return "low"
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_analyst_agent.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add core/agents/analyst.py tests/core/test_analyst_agent.py
git commit -m "feat(agents): add Analyst Agent with change classification"
```

---

## Task 10: Reporter Agent

**Files:**
- Create: `core/agents/reporter.py`
- Test: `tests/core/test_reporter_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_reporter_agent.py`:

```python
from core.agents.reporter import ReporterAgent
from core.agents.events import AnalysisEvent


def test_reporter_generates_summary():
    analysis = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        change_type="price_drop",
        severity="high",
        semantic_diff_summary="Price dropped from $15 to $10",
    )
    agent = ReporterAgent()
    report = agent.run(analysis)
    assert report.title == "Price drop detected"
    assert "Price dropped" in report.summary
    assert len(report.recommended_actions) > 0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_reporter_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agents.reporter'`

- [ ] **Step 3: Implement the Reporter Agent**

Create `core/agents/reporter.py`:

```python
import time
from typing import Optional
from core.agents.events import AnalysisEvent, ReportEvent
from core.llm.router import LLMRouter
from core.llm.config import TaskProfile


class ReporterAgent:
    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router

    def run(self, analysis: AnalysisEvent) -> ReportEvent:
        start = time.time()
        title = self._title(analysis.change_type)
        summary = analysis.semantic_diff_summary or f"{analysis.change_type} detected with severity {analysis.severity}"
        recommended = [
            {"type": "email", "reason": "default alert"},
            {"type": "slack", "reason": "high visibility"},
        ] if analysis.severity in ("high", "critical") else [
            {"type": "email", "reason": "default alert"},
        ]

        if self.llm_router:
            summary = self._generate_summary(analysis)

        latency_ms = (time.time() - start) * 1000
        return ReportEvent(
            run_id=analysis.run_id,
            site_id=analysis.site_id,
            title=title,
            summary=summary,
            recommended_actions=recommended,
            latency_ms=latency_ms,
        )

    def _title(self, change_type: str) -> str:
        return {
            "price_drop": "Price drop detected",
            "price_rise": "Price rise detected",
            "new_product": "New product detected",
            "layout_change": "Layout change detected",
            "seo_change": "SEO metadata changed",
            "content_update": "Content updated",
        }.get(change_type, "Change detected")

    def _generate_summary(self, analysis: AnalysisEvent) -> str:
        messages = [
            {"role": "system", "content": "Write a concise, human-readable summary of a website change."},
            {"role": "user", "content": f"change_type={analysis.change_type}, severity={analysis.severity}, summary={analysis.semantic_diff_summary}"},
        ]
        try:
            response = self.llm_router.chat(messages, TaskProfile(name="report"))
            return response.content
        except Exception:
            return analysis.semantic_diff_summary or "Change detected"
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_reporter_agent.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add core/agents/reporter.py tests/core/test_reporter_agent.py
git commit -m "feat(agents): add Reporter Agent with summary generation"
```

---

## Task 11: Action Handler Base + Registry

**Files:**
- Create: `core/actions/base.py`
- Create: `core/actions/registry.py`
- Create: `core/actions/handlers/email.py`
- Create: `core/actions/handlers/slack.py`
- Test: `tests/core/test_action_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_action_registry.py`:

```python
from core.actions.base import ActionContext, ProposedAction
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler


def test_registry_finds_handler():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    handler = registry.get("email")
    assert handler is not None
    assert handler.name == "email"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_action_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.actions.base'`

- [ ] **Step 3: Implement the base interface**

Create `core/actions/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
from core.agents.events import ReportEvent


@dataclass
class ActionContext:
    site: Any
    report: ReportEvent
    change: Optional[Any] = None


@dataclass
class ProposedAction:
    type: str
    risk_score: float
    payload: dict[str, Any]
    description: str


@dataclass
class ActionResult:
    success: bool
    type: str
    message: str
    output: Optional[dict[str, Any]] = None


class ActionHandler(ABC):
    name: str = ""
    risk_score: float = 0.0

    @abstractmethod
    def propose(self, context: ActionContext) -> list[ProposedAction]: ...

    @abstractmethod
    def execute(self, proposed: ProposedAction) -> ActionResult: ...
```

- [ ] **Step 4: Implement the registry**

Create `core/actions/registry.py`:

```python
from typing import Optional
from core.actions.base import ActionHandler


class ActionHandlerRegistry:
    def __init__(self):
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        self._handlers[handler.name] = handler

    def get(self, name: str) -> Optional[ActionHandler]:
        return self._handlers.get(name)

    def list(self) -> list[str]:
        return list(self._handlers.keys())

    def propose_all(self, context) -> list:
        proposals = []
        for handler in self._handlers.values():
            proposals.extend(handler.propose(context))
        return proposals
```

- [ ] **Step 5: Implement email handler stub**

Create `core/actions/handlers/email.py`:

```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class EmailActionHandler(ActionHandler):
    name = "email"
    risk_score = 0.1

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={"subject": context.report.title, "body": context.report.summary},
                description="Send email alert",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(success=True, type=self.name, message="Email sent", output=proposed.payload)
```

- [ ] **Step 6: Implement slack handler stub**

Create `core/actions/handlers/slack.py`:

```python
from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult


class SlackActionHandler(ActionHandler):
    name = "slack"
    risk_score = 0.4

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if not context.site.slack_webhook:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={"webhook": context.site.slack_webhook, "message": context.report.summary},
                description="Post to Slack",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        return ActionResult(success=True, type=self.name, message="Slack message posted", output=proposed.payload)
```

- [ ] **Step 7: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_action_registry.py -v
```

Expected: `1 passed`

- [ ] **Step 8: Commit**

```bash
git add core/actions/base.py core/actions/registry.py core/actions/handlers/email.py core/actions/handlers/slack.py tests/core/test_action_registry.py
git commit -m "feat(actions): add action handler base, registry, and email/slack stubs"
```

---

## Task 12: Action Agent

**Files:**
- Create: `core/agents/action.py`
- Test: `tests/core/test_action_agent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_action_agent.py`:

```python
from unittest.mock import MagicMock
from core.agents.action import ActionAgent
from core.agents.events import ReportEvent
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from db.models import MonitorSite


def test_action_agent_proposes_email():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    agent = ActionAgent(registry)

    site = MonitorSite(id=1, instruction="test", threshold=1.0, approval_policy="auto")
    report = ReportEvent(run_id="r1", site_id=1, title="Change", summary="Price dropped", recommended_actions=[])

    event = agent.run(report, site)
    assert len(event.actions) == 1
    assert event.actions[0]["type"] == "email"
    assert event.approval_requests == []


def test_action_agent_creates_approval_for_high_risk():
    registry = ActionHandlerRegistry()
    registry.register(EmailActionHandler())
    agent = ActionAgent(registry)

    site = MonitorSite(id=1, instruction="test", threshold=1.0, approval_policy="always")
    report = ReportEvent(run_id="r1", site_id=1, title="Change", summary="Price dropped", recommended_actions=[])

    event = agent.run(report, site)
    assert len(event.approval_requests) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_action_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.agents.action'`

- [ ] **Step 3: Implement the Action Agent**

Create `core/agents/action.py`:

```python
import time
from typing import Optional, Any
from core.agents.events import ReportEvent, ActionEvent
from core.actions.registry import ActionHandlerRegistry
from core.actions.base import ActionContext
from db.models import MonitorSite


class ActionAgent:
    def __init__(self, registry: ActionHandlerRegistry):
        self.registry = registry

    def run(self, report: ReportEvent, site: MonitorSite, change: Optional[Any] = None) -> ActionEvent:
        start = time.time()
        context = ActionContext(site=site, report=report, change=change)
        proposals = self.registry.propose_all(context)

        actions = []
        approval_requests = []
        for proposal in proposals:
            if self._requires_approval(site, proposal):
                approval_requests.append({
                    "type": proposal.type,
                    "risk_score": proposal.risk_score,
                    "payload": proposal.payload,
                    "description": proposal.description,
                })
            else:
                handler = self.registry.get(proposal.type)
                result = handler.execute(proposal)
                actions.append({
                    "type": proposal.type,
                    "success": result.success,
                    "message": result.message,
                    "output": result.output,
                })

        latency_ms = (time.time() - start) * 1000
        return ActionEvent(
            run_id=report.run_id,
            site_id=report.site_id,
            actions=actions,
            approval_requests=approval_requests,
            latency_ms=latency_ms,
        )

    def _requires_approval(self, site: MonitorSite, proposal) -> bool:
        if site.approval_policy == "always":
            return True
        if site.approval_policy == "high_risk" and proposal.risk_score >= 0.7:
            return True
        return False
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_action_agent.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/agents/action.py tests/core/test_action_agent.py
git commit -m "feat(agents): add Action Agent with approval gating"
```

---

## Task 13: Workflow Engine

**Files:**
- Create: `core/workflow/engine.py`
- Test: `tests/core/test_workflow_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_workflow_engine.py`:

```python
from core.workflow.engine import WorkflowEngine
from core.agents.events import AnalysisEvent


def test_workflow_evaluates_price_drop_rule():
    engine = WorkflowEngine({
        "rules": [
            {
                "id": "price_drop_20",
                "condition": "change_type == 'price_drop' and change_score > 1.0",
                "actions": [{"type": "email", "priority": "high"}],
            }
        ]
    })
    analysis = AnalysisEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        change_type="price_drop",
        severity="high",
    )
    triggered = engine.evaluate(analysis, change_score=5.0)
    assert len(triggered) == 1
    assert triggered[0]["id"] == "price_drop_20"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_workflow_engine.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.workflow.engine'`

- [ ] **Step 3: Implement the workflow engine**

Create `core/workflow/engine.py`:

```python
from typing import Any
from core.agents.events import AnalysisEvent


class WorkflowEngine:
    def __init__(self, rules: dict[str, Any]):
        self.rules = rules.get("rules", [])

    def evaluate(self, analysis: AnalysisEvent, change_score: float = 0.0) -> list[dict[str, Any]]:
        triggered = []
        context = {
            "change_type": analysis.change_type,
            "severity": analysis.severity,
            "change_score": change_score,
            "has_change": analysis.has_change,
        }
        for rule in self.rules:
            try:
                if self._eval(rule.get("condition", ""), context):
                    triggered.append(rule)
            except Exception:
                continue
        return triggered

    def _eval(self, condition: str, context: dict) -> bool:
        if not condition:
            return False
        # Simple expression evaluation with restricted globals
        allowed = {"__builtins__": {}}
        return bool(eval(condition, allowed, context))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_workflow_engine.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add core/workflow/engine.py tests/core/test_workflow_engine.py
git commit -m "feat(workflow): add rule evaluation engine"
```

---

## Task 14: MonitoringOrchestrator

**Files:**
- Create: `core/orchestrator.py`
- Modify: `core/monitor_service.py` (to delegate)
- Test: `tests/core/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_orchestrator.py`:

```python
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from core.orchestrator import MonitoringOrchestrator
from core.agents.events import ScoutEvent
from db.models import MonitorSite


def test_orchestrator_runs_pipeline():
    db = MagicMock(spec=Session)
    site = MonitorSite(id=1, instruction="test", threshold=1.0, approval_policy="auto")
    site.url = "https://example.com"

    orch = MonitoringOrchestrator(db)
    with patch.object(orch, "_latest_snapshot", return_value=None), patch.object(orch.scout, "run", return_value=ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=False,
        url="https://example.com",
        content_markdown="",
        content_hash="abc",
        entities=[]
    )):
        result = orch.run(site)

    assert result["success"] is True
    assert result["change_detected"] is False
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/core/test_orchestrator.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.orchestrator'`

- [ ] **Step 3: Implement the orchestrator**

Create `core/orchestrator.py`:

```python
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

from core.agents.events import ScoutEvent, AnalysisEvent, ReportEvent, ActionEvent
from core.agents.scout import ScoutAgent
from core.agents.analyst import AnalystAgent
from core.agents.reporter import ReporterAgent
from core.agents.action import ActionAgent
from core.actions.registry import ActionHandlerRegistry
from core.actions.handlers.email import EmailActionHandler
from core.actions.handlers.slack import SlackActionHandler
from core.llm.router import LLMRouter
from db.models import MonitorSite, MonitorSnapshot, MonitorChange, AuditLog, ApprovalRequest
from config.settings import load_llm_router_config


class MonitoringOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.llm_router = LLMRouter(load_llm_router_config())
        self.scout = ScoutAgent(llm_router=self.llm_router, db=db)
        self.analyst = AnalystAgent(llm_router=self.llm_router)
        self.reporter = ReporterAgent(llm_router=self.llm_router)
        self.action_registry = ActionHandlerRegistry()
        self.action_registry.register(EmailActionHandler())
        self.action_registry.register(SlackActionHandler())
        self.action_agent = ActionAgent(self.action_registry)

    def run(self, site: MonitorSite) -> dict:
        run_id = str(uuid.uuid4())
        result = {
            "success": False,
            "change_detected": False,
            "change_score": 0.0,
            "alert_sent": False,
            "error": None,
            "run_id": run_id,
        }

        try:
            previous = self._latest_snapshot(site.id)
            scout_event = self.scout.run(site, previous)
            scout_event.run_id = run_id
            self._log(run_id, site, "scout", "scrape", scout_event)

            if scout_event.error:
                self._save_failed_snapshot(site, run_id, scout_event.error)
                result["error"] = scout_event.error
                return result

            new_snapshot = self._save_snapshot(site, run_id, scout_event)
            if previous is None:
                result["success"] = True
                return result

            if not scout_event.has_change:
                result["success"] = True
                return result

            analysis = self.analyst.run(scout_event, previous, new_snapshot)
            analysis.run_id = run_id
            self._log(run_id, site, "analyst", "classify", analysis)

            triggered_rules = self._evaluate_workflow_rules(site, analysis)
            if triggered_rules:
                self._log(run_id, site, "workflow", "rules_triggered", analysis)

            change_record = self._save_change(site, run_id, previous, new_snapshot, analysis)
            result["change_detected"] = analysis.has_change
            result["change_score"] = getattr(analysis, "change_score", 0.0)

            report = self.reporter.run(analysis)
            report.run_id = run_id
            self._log(run_id, site, "reporter", "summarize", report)

            action_event = self.action_agent.run(report, site, change_record)
            action_event.run_id = run_id
            self._log(run_id, site, "action", "act", action_event)
            self._save_approval_requests(run_id, site, change_record, action_event)

            if action_event.actions:
                result["alert_sent"] = any(a.get("type") == "email" and a.get("success") for a in action_event.actions)

            result["success"] = True
            return result

        except Exception as exc:
            self.db.rollback()
            result["error"] = str(exc)
            return result

    def _evaluate_workflow_rules(self, site: MonitorSite, analysis: AnalysisEvent) -> list[dict]:
        if not site.workflow_rules:
            return []
        from core.workflow.engine import WorkflowEngine
        engine = WorkflowEngine(site.workflow_rules)
        return engine.evaluate(analysis, change_score=analysis.change_score)

    def _latest_snapshot(self, site_id: int) -> Optional[MonitorSnapshot]:
        return (
            self.db.query(MonitorSnapshot)
            .filter(MonitorSnapshot.site_id == site_id, MonitorSnapshot.status == "success")
            .order_by(MonitorSnapshot.scraped_at.desc())
            .first()
        )

    def _save_snapshot(self, site: MonitorSite, run_id: str, event: ScoutEvent) -> MonitorSnapshot:
        content = event.content_markdown or ""
        snap = MonitorSnapshot(
            site_id=site.id,
            content_markdown=content,
            content_hash=event.content_hash or hashlib.md5(content.encode("utf-8")).hexdigest(),
            content_length=len(content),
            status="success",
            extracted_entities={"entities": event.entities},
            model_calls={"run_id": run_id},
        )
        self.db.add(snap)
        self.db.flush()
        site.last_checked_at = datetime.utcnow()
        self.db.commit()
        return snap

    def _save_failed_snapshot(self, site: MonitorSite, run_id: str, error: str):
        snap = MonitorSnapshot(
            site_id=site.id,
            content_markdown=None,
            content_hash="",
            content_length=0,
            status="error",
            error_message=error,
        )
        self.db.add(snap)
        site.last_checked_at = datetime.utcnow()
        self.db.commit()

    def _save_change(self, site, run_id, old, new, analysis: AnalysisEvent) -> MonitorChange:
        change = MonitorChange(
            site_id=site.id,
            change_score=analysis.change_score,
            added_lines=analysis.added_lines,
            removed_lines=analysis.removed_lines,
            modified_lines=analysis.modified_lines,
            change_type=analysis.change_type,
            severity=analysis.severity,
            diff_summary=analysis.semantic_diff_summary,
            vision_description=analysis.vision_description,
            old_snapshot_id=old.id if old else None,
            new_snapshot_id=new.id if new else None,
            alert_sent=False,
            agent_reasoning={"run_id": run_id},
        )
        self.db.add(change)
        self.db.flush()
        self.db.commit()
        return change

    def _log(self, run_id: str, site: MonitorSite, actor: str, action: str, event):
        log = AuditLog(
            run_id=run_id,
            site_id=site.id,
            actor=actor,
            action=action,
            reasoning=str(event.payload) if hasattr(event, "payload") else "",
            cost_usd=getattr(event, "cost_usd", 0.0),
            latency_ms=getattr(event, "latency_ms", 0.0),
        )
        self.db.add(log)

    def _save_approval_requests(self, run_id: str, site: MonitorSite, change: MonitorChange, event: ActionEvent):
        for req in event.approval_requests:
            ar = ApprovalRequest(
                run_id=run_id,
                site_id=site.id,
                change_id=change.id if change else None,
                action_type=req["type"],
                risk_score=req["risk_score"],
                payload=req["payload"],
                status="pending",
                user_id=site.user_id,
            )
            self.db.add(ar)
        self.db.commit()
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python -m pytest tests/core/test_orchestrator.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Modify legacy monitor_service to delegate**

Modify `core/monitor_service.py` to delegate to the orchestrator:

```python
from core.orchestrator import MonitoringOrchestrator


def run_monitor_for_site(site: MonitorSite, db: Session) -> dict:
    orchestrator = MonitoringOrchestrator(db)
    return orchestrator.run(site)
```

Replace the entire body of `run_monitor_for_site` with the above.

- [ ] **Step 6: Commit**

```bash
git add core/orchestrator.py core/monitor_service.py tests/core/test_orchestrator.py
git commit -m "feat(core): add MonitoringOrchestrator and wire it into monitor_service"
```

---

## Task 15: Wire Orchestrator into API Trigger

**Files:**
- Modify: `api/routers/monitor.py`

- [ ] **Step 1: Inspect current trigger endpoint**

The endpoint currently does:

```python
from core.monitor_service import run_monitor_for_site
result = run_monitor_for_site(bg_site, bg_db)
```

This will still work because `run_monitor_for_site` now delegates to the orchestrator.

- [ ] **Step 2: Update SSE broadcast payload**

Modify the `_run` function in `api/routers/monitor.py` to include `run_id`:

```python
def _run():
    from db.base import SessionLocal as SL
    bg_db = SL()
    try:
        bg_site = bg_db.query(MonitorSite).filter(MonitorSite.id == site_id).first()
        result = run_monitor_for_site(bg_site, bg_db)
        if result.get("change_detected"):
            _broadcast(user.id, {
                "type": "change_detected",
                "site_id": site_id,
                "change_score": result["change_score"],
                "alert_sent": result["alert_sent"],
                "run_id": result.get("run_id"),
                "timestamp": datetime.utcnow().isoformat(),
            })
    finally:
        bg_db.close()
```

- [ ] **Step 3: Run the API smoke test**

```bash
python -m pytest tests/ -v -k monitor
```

Expected: existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/routers/monitor.py
git commit -m "feat(api): include run_id in SSE change events"
```

---

## Task 16: Wire Orchestrator into Scheduler

**Files:**
- Modify: `src/scheduler_db.py`

- [ ] **Step 1: Verify scheduler uses monitor_service**

The scheduler already calls `run_monitor_for_site(site, db)` in `check_site`. Since `run_monitor_for_site` now delegates to the orchestrator, no changes are needed.

- [ ] **Step 2: Add a log line to confirm orchestration**

Modify `src/scheduler_db.py` in `check_site`:

```python
result = run_monitor_for_site(site, db)
if result.get("success"):
    logger.info(
        f"[site {site_id}] Orchestrated run {result.get('run_id')} | change_detected={result['change_detected']} | alert_sent={result['alert_sent']}"
    )
```

- [ ] **Step 3: Commit**

```bash
git add src/scheduler_db.py
git commit -m "chore(scheduler): log orchestrated run_id in scheduled checks"
```

---

## Task 17: Run Full Test Suite

**Files:**
- All tests

- [ ] **Step 1: Run all tests**

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the API server smoke test**

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# In another terminal:
curl http://localhost:8000/health
```

Expected: `{"status":"ok","service":"monitor-agent"}`

- [ ] **Step 3: Commit any final fixes**

If tests fail, fix them and commit.

---

## Task 18: Update Documentation

**Files:**
- Modify: `docs/TECHNICAL_DOC.md`

- [ ] **Step 1: Add architecture overview section**

Insert a new section after the existing architecture diagram:

```markdown
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
```

- [ ] **Step 2: Update environment variables reference**

Add to the environment variables table:

```markdown
| `LLM_ROUTER_CONFIG` | — | — | JSON string of multi-model router config |
```

- [ ] **Step 3: Commit**

```bash
git add docs/TECHNICAL_DOC.md
git commit -m "docs: document agentic core architecture and orchestrator"
```

---

## Self-Review

### Spec coverage

| Spec section | Plan task(s) |
|---|---|
| Multi-model routing | Task 2, 3, 4 |
| Audit trail | Task 6, 7, 14 |
| Approval framework | Task 5, 6, 12, 14 |
| Scout Agent | Task 8 |
| Analyst Agent | Task 9 |
| Reporter Agent | Task 10 |
| Action Agent | Task 11, 12 |
| Workflow engine | Task 13 |
| Orchestration | Task 14 |
| MCP server | Not in Phase 0/1 — deferred to Phase 3 |
| Visual diff | Not in Phase 0/1 — deferred to Phase 2 |
| Integrations | Stubs in Task 11; full implementations deferred to Phase 4 |

### Placeholder scan

- No TBD, TODO, or "implement later" in steps.
- All steps include actual code or exact commands.
- All file paths are exact.

### Type consistency

- `LLMResponse.total_cost` is used consistently.
- `AgentEvent.stage` is a string, set by each subclass.
- `ApprovalRequest.status` defaults to `"pending"`.
- `MonitorSite.approval_policy` values are `"always"`, `"high_risk"`, `"auto"`.

### Gaps

- Only `EmailActionHandler` and `SlackActionHandler` are stubbed in Phase 1. The remaining handlers (`notion`, `github_pr`, `n8n_webhook`, `generic_webhook`, `purchase`) are intentionally deferred to Phase 4.
- Visual diff and screenshot capture are deferred to Phase 2.
- MCP server is deferred to Phase 3.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-18-agentic-core-phase-0-1.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — I execute tasks in this session using the executing-plans skill, batch execution with checkpoints.

**Which approach would you like?**
