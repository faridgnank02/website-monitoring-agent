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
