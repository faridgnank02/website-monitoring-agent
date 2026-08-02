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
