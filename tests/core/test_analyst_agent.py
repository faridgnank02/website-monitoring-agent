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


def test_no_old_snapshot_returns_no_change():
    agent = AnalystAgent(llm_router=MagicMock())
    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )
    new_snap = MagicMock()
    new_snap.content_markdown = "content"
    new_snap.extracted_entities = []

    result = agent.run(scout, None, new_snap)

    assert result.has_change is False
    assert result.change_type == "content_update"
    assert result.severity == "low"


def test_no_changes_returns_content_update_low_severity():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=False,
            change_score=0.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[],
            diff_summary="No changes",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="old",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.has_change is False
    assert result.change_type == "content_update"
    assert result.severity == "low"


def test_price_rise():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99", unit="USD")]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $22.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="22.99", unit="USD")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[Entity(entity_id="t-shirt", name="T-Shirt", value="22.99", unit="USD")]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=2.0,
            added_lines=[],
            removed_lines=[],
            modified_lines=[("T-Shirt $19.99", "T-Shirt $22.99")],
            diff_summary="Price changed",
            total_lines_old=1,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "price_rise"
    assert result.severity == "high"


def test_dict_entities_from_db_json():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99"
    old_snap.extracted_entities = {"entities": [{"entity_id": "t-shirt", "name": "T-Shirt", "value": "19.99", "unit": "USD"}]}

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $17.99"
    new_snap.extracted_entities = {"entities": [{"entity_id": "t-shirt", "name": "T-Shirt", "value": "17.99", "unit": "USD"}]}

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com",
        entities=[{"entity_id": "t-shirt", "name": "T-Shirt", "value": "17.99", "unit": "USD"}]
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


def test_removed_entity():
    agent = AnalystAgent(llm_router=MagicMock())

    old_snap = MagicMock()
    old_snap.content_markdown = "T-Shirt $19.99\nJeans $49.99"
    old_snap.extracted_entities = [
        Entity(entity_id="t-shirt", name="T-Shirt", value="19.99"),
        Entity(entity_id="jeans", name="Jeans", value="49.99"),
    ]

    new_snap = MagicMock()
    new_snap.content_markdown = "T-Shirt $19.99"
    new_snap.extracted_entities = [Entity(entity_id="t-shirt", name="T-Shirt", value="19.99")]

    scout = ScoutEvent(
        run_id="r1", site_id=1, has_change=True, url="https://example.com", entities=[]
    )

    with patch("core.agents.analyst.compare_content") as mock_compare:
        mock_compare.return_value = ComparisonResult(
            has_changes=True,
            change_score=0.5,
            added_lines=[],
            removed_lines=["Jeans $49.99"],
            modified_lines=[],
            diff_summary="Removed Jeans",
            total_lines_old=2,
            total_lines_new=1,
            hash_old="old",
            hash_new="new",
        )
        result = agent.run(scout, old_snap, new_snap)

    assert result.change_type == "content_update"
