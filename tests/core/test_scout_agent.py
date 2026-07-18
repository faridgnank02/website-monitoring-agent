from unittest.mock import patch, MagicMock
from core.agents.scout import ScoutAgent
from db.models import MonitorSite


def make_site():
    return MonitorSite(id=1, user_id=1, instruction="monitor prices on example.com", threshold=1.0)


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
