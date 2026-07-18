"""
SQLAlchemy ORM models for Monitor Agent.
All tables in a single file for clarity at this stage.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sites: Mapped[list["MonitorSite"]] = relationship("MonitorSite", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Monitor Sites
# ---------------------------------------------------------------------------

class MonitorSite(Base):
    __tablename__ = "monitor_sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)  # natural language instruction
    url: Mapped[Optional[str]] = mapped_column(String(2048))         # parsed URL (filled after first AI parse)
    threshold: Mapped[float] = mapped_column(Float, default=1.0)     # % change to trigger alert
    schedule_cron: Mapped[str] = mapped_column(String(100), default="0 */6 * * *")  # every 6h
    use_case: Mapped[str] = mapped_column(String(100), default="general")
    # use_case: ecommerce_pricing | ecommerce_stock | regulatory | press | competitor | general
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_change_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    monitor_mode: Mapped[str] = mapped_column(String(50), default="standard")
    scrape_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    workflow_rules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    approval_policy: Mapped[str] = mapped_column(String(50), default="high_risk")
    # TODO: encrypt these tokens at rest using core.security.encryption before storing
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


# ---------------------------------------------------------------------------
# Snapshots — stores the full markdown content (THE key fix vs. old code)
# ---------------------------------------------------------------------------

class MonitorSnapshot(Base):
    __tablename__ = "monitor_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    content_markdown: Mapped[Optional[str]] = mapped_column(Text)    # full content stored here
    content_hash: Mapped[str] = mapped_column(String(32), index=True)
    content_length: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="success")  # success | error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scrape_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    dom_json_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_calls: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    site: Mapped["MonitorSite"] = relationship("MonitorSite", back_populates="snapshots")


# ---------------------------------------------------------------------------
# Changes — diff results between two snapshots
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Notification log
# ---------------------------------------------------------------------------

class NotificationLog(Base):
    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_sites.id"), nullable=True)
    change_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("monitor_changes.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))   # change_alert | error | digest
    channel: Mapped[str] = mapped_column(String(50))       # email | slack | sse
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# Audit logs — agentic run traceability
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Approval requests — human-in-the-loop gating
# ---------------------------------------------------------------------------

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
