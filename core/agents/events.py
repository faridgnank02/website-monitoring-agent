from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

from core.entities.models import Entity, CorrelatedEntity


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
    entities: list[Entity] = Field(default_factory=list)
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
    correlated_entities: list[CorrelatedEntity] = Field(default_factory=list)


class ReportEvent(AgentEvent):
    stage: str = "reporter"
    title: str
    summary: str
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)


class ActionEvent(AgentEvent):
    stage: str = "action"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    approval_requests: list[dict[str, Any]] = Field(default_factory=list)
