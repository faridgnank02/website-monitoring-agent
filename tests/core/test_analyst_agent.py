from unittest.mock import MagicMock, patch
from core.agents.analyst import AnalystAgent
from core.agents.events import ScoutEvent
from core.entities.models import Entity
from src.modules.content_comparator import ComparisonResult


def test_analyst_classifies_price_drop():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $17.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="t-shirt", name="T-Shirt", value="17.99", unit="USD")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $17.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_drop"
    assert result.severity == "high"
    assert result.correlated_entities[0].changed is True


def test_analyst_classifies_new_product():
    llm_router = MagicMock()
    agent = AnalystAgent(llm_router=llm_router)

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99\nJeans $49.99"
    new_snap.extracted_entities = [
        Entity(entity_id="t-shirt", name="T-Shirt", value="19.99"),
        Entity(entity_id="jeans", name="Jeans", value="49.99"),
    ]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="jeans", name="Jeans", value="49.99")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=0.5,
            added_lines=["Jeans $49.99"],
            removed_lines=[],
            modified_lines=[],
            diff_summary="Added Jeans",
            total_lines_old=1,
            total_lines_new=2,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "new_product"
