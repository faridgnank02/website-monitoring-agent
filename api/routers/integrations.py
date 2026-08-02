"""
Integrations management routes.

Per-site action config (actions_enabled, integration_config) and integration
credentials. Tokens are encrypted at rest; responses only return masked values.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from db.models import User, MonitorSite
from core.security.site_encryption import (
    encrypt_site_token,
    mask_token,
    resolve_token,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class IntegrationsUpdate(BaseModel):
    actions_enabled: Optional[List[str]] = None
    integration_config: Optional[dict] = None
    slack_webhook: Optional[str] = None
    notion_token: Optional[str] = None
    github_token: Optional[str] = None
    n8n_webhook_url: Optional[str] = None


class IntegrationsOut(BaseModel):
    site_id: int
    actions_enabled: List[str] = Field(default_factory=list)
    integration_config: dict = Field(default_factory=dict)
    slack_webhook_masked: str = ""
    notion_token_masked: str = ""
    github_token_masked: str = ""
    n8n_webhook_url_masked: str = ""


_TOKEN_FIELDS = [
    "slack_webhook",
    "notion_token",
    "github_token",
    "n8n_webhook_url",
]

_WEBHOOK_SECRET_FIELD = "webhook.secret"


def _encrypt_integration_secrets(site_id: int, config: dict) -> dict:
    """Encrypt any secret stored inside integration_config (e.g. webhook.secret), in place."""
    if not config:
        return config
    if "webhook" in config and isinstance(config["webhook"], dict):
        secret = config["webhook"].get("secret") or ""
        if secret and not secret.startswith("gAAAA"):
            config["webhook"]["secret"] = encrypt_site_token(site_id, secret)
    return config


def _mask_integration_config(site: MonitorSite, config: dict) -> dict:
    """Return a copy of integration_config with secrets masked, never leaking them."""
    masked = dict(config)
    if "webhook" in masked and isinstance(masked["webhook"], dict):
        webhook = dict(masked["webhook"])
        secret = webhook.get("secret") or ""
        if secret:
            try:
                webhook["secret"] = mask_token(resolve_token(site.id, secret))
            except ValueError:
                webhook["secret"] = ""
        masked["webhook"] = webhook
    return masked


def _get_site_or_404(site_id: int, user_id: int, db: Session) -> MonitorSite:
    site = db.query(MonitorSite).filter(
        MonitorSite.id == site_id,
        MonitorSite.user_id == user_id,
    ).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


def _masked(site: MonitorSite) -> IntegrationsOut:
    masked_fields = {}
    for field in _TOKEN_FIELDS:
        value = getattr(site, field) or ""
        try:
            masked_fields[f"{field}_masked"] = mask_token(resolve_token(site.id, value))
        except ValueError:
            masked_fields[f"{field}_masked"] = ""
    return IntegrationsOut(
        site_id=site.id,
        actions_enabled=site.actions_enabled or [],
        integration_config=_mask_integration_config(site, site.integration_config or {}),
        **masked_fields,
    )


@router.get("/sites/{site_id}", response_model=IntegrationsOut)
def get_site_integrations(
    site_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)
    return _masked(site)


@router.put("/sites/{site_id}", response_model=IntegrationsOut)
def update_site_integrations(
    site_id: int,
    body: IntegrationsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    site = _get_site_or_404(site_id, user.id, db)
    data = body.model_dump(exclude_none=True)

    for field in _TOKEN_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None or value == "":
            setattr(site, field, "")
            continue
        if value.startswith("gAAAA"):
            try:
                resolve_token(site.id, value)
            except ValueError:
                value = encrypt_site_token(site.id, value)
            setattr(site, field, value)
        else:
            setattr(site, field, encrypt_site_token(site.id, value))

    if "actions_enabled" in data:
        site.actions_enabled = data["actions_enabled"]
    if "integration_config" in data:
        site.integration_config = _encrypt_integration_secrets(site.id, data["integration_config"])

    db.commit()
    db.refresh(site)
    return _masked(site)
