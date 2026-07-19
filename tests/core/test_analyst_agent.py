from unittest.mock import MagicMock
from core.agents.analyst import AnalystAgent
from core.agents.events import ScoutEvent
from core.entities.models import Entity
from db.models import MonitorSnapshot


def test_analyst_classifies_price_drop():
    scout = ScoutEvent(
        run_id="r1",
        site_id=1,
        has_change=True,
        snapshot_id=2,
        url="https://example.com",
        entities=[Entity(entity_id="price", name="price", value="$10", old_value="$15")],
    )
    old = MonitorSnapshot(id=1, site_id=1, content_markdown="Price $15", content_hash="a")
    new = MonitorSnapshot(id=2, site_id=1, content_markdown="Price $10", content_hash="b")

    agent = AnalystAgent()
    event = agent.run(scout, old, new)

    assert event.has_change is True
    assert event.change_type == "price_drop"
    assert event.severity == "high"
