from unittest.mock import patch, MagicMock
from core.agents.scout import ScoutAgent
from core.entities.models import Entity
from db.models import MonitorSite


def make_site():
    return MonitorSite(id=1, user_id=1, instruction="monitor prices on example.com", threshold=1.0)


def test_scout_detects_first_snapshot():
    mock_parse = MagicMock(
        return_value=MagicMock(success=True, url="https://example.com", elements_to_watch=["prices"])
    )
    mock_scrape = MagicMock(
        return_value=MagicMock(
            success=True,
            markdown="# Example\nPrice: $10",
            html="<html></html>",
            metadata={},
            timestamp=0,
        )
    )

    agent = ScoutAgent(parse_instruction=mock_parse, scrape_url=mock_scrape)
    event = agent.run(make_site(), previous_snapshot=None)

    assert event.has_change is True
    assert event.url == "https://example.com"
    assert event.entities == []


def test_scout_extracts_and_returns_entities():
    site = MagicMock()
    site.id = 1
    site.instruction = "Monitor price of T-Shirt"
    site.url = "https://example.com"

    parsed = MagicMock(success=True, url="https://example.com", error=None)
    scraped = MagicMock(success=True, markdown="T-Shirt $19.99", html="", metadata={}, error=None)
    entity = Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")

    mock_parse = MagicMock(return_value=parsed)
    mock_scrape = MagicMock(return_value=scraped)

    with patch("core.agents.scout.extract_entities", return_value=[entity]):
        agent = ScoutAgent(
            llm_router=MagicMock(),
            db=MagicMock(),
            parse_instruction=mock_parse,
            scrape_url=mock_scrape,
        )
        event = agent.run(site, previous_snapshot=None)

    assert event.has_change is True
    assert event.entities == [entity]
