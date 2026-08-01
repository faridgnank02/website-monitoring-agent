import requests

from core.actions.base import ActionHandler, ActionContext, ProposedAction, ActionResult
from core.security.site_encryption import resolve_token


class GitHubActionHandler(ActionHandler):
    name = "github"
    risk_score = 0.5

    def _repo(self, context: ActionContext) -> str:
        cfg = (getattr(context.site, "integration_config", None) or {}).get("github", {})
        return cfg.get("repo", "") or ""

    def propose(self, context: ActionContext) -> list[ProposedAction]:
        if self.name not in (getattr(context.site, "actions_enabled", None) or []):
            return []
        if not getattr(context.site, "github_token", None):
            return []
        repo = self._repo(context)
        if not repo:
            return []
        return [
            ProposedAction(
                type=self.name,
                risk_score=self.risk_score,
                payload={
                    "token": context.site.github_token,
                    "site_id": getattr(context.site, "id", None),
                    "repo": repo,
                    "title": context.report.title,
                    "body": context.report.summary,
                },
                description="Create GitHub issue",
            )
        ]

    def execute(self, proposed: ProposedAction) -> ActionResult:
        payload = proposed.payload
        try:
            token = resolve_token(payload.get("site_id"), payload.get("token", ""))
            repo = payload.get("repo", "")
            url = f"https://api.github.com/repos/{repo}/issues"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            }
            body = {
                "title": payload.get("title", "Monitor Agent alert"),
                "body": payload.get("body", ""),
            }
            response = requests.post(url, headers=headers, json=body, timeout=10)
            if response.status_code >= 400:
                return ActionResult(
                    success=False,
                    type=self.name,
                    message=f"GitHub returned HTTP {response.status_code}",
                )
            external_id = str(response.json().get("number", ""))
            return ActionResult(
                success=True,
                type=self.name,
                message="GitHub issue created",
                output={"external_id": external_id},
            )
        except Exception:
            return ActionResult(success=False, type=self.name, message="GitHub issue creation failed")
