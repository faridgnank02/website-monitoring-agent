from core.entities.models import Entity
from core.entities.correlator import correlate_entities


def test_unchanged_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].changed is False
    assert result[0].status == "unchanged"


def test_changed_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [Entity(entity_id="prod-1", name="T-Shirt", value="17.99")]
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].changed is True
    assert result[0].old_value == "19.99"
    assert result[0].new_value == "17.99"


def test_added_and_removed_entities():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = [
        Entity(entity_id="prod-1", name="T-Shirt", value="19.99"),
        Entity(entity_id="prod-2", name="Jeans", value="49.99"),
    ]
    result = correlate_entities(old, new)
    assert len(result) == 2
    statuses = {r.entity_id: r.status for r in result}
    assert statuses["prod-1"] == "unchanged"
    assert statuses["prod-2"] == "added"


def test_removed_entity():
    old = [Entity(entity_id="prod-1", name="T-Shirt", value="19.99")]
    new = []
    result = correlate_entities(old, new)
    assert len(result) == 1
    assert result[0].status == "removed"
    assert result[0].old_value == "19.99"
